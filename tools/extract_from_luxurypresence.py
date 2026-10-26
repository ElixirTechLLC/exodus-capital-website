#!/usr/bin/env python3
"""
One-time (re-runnable) extraction of content from a saved copy of the
Luxury Presence site into data/*.json and static/media/.

Usage:
    python3 tools/extract_from_luxurypresence.py <snapshot-dir> <website-dir>

<snapshot-dir> must contain: home.html, team.html, listings.html, blog.html,
careers.html, testimonials.html, properties_track-record.html,
properties/<slug>.html, agents/<slug>.html, blog/<slug>.html

Only the Python standard library + curl + `file` are used.
"""
import html, json, pathlib, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

SRC = pathlib.Path(sys.argv[1]).resolve()
OUT = pathlib.Path(sys.argv[2]).resolve()
DATA = OUT / "data"
MEDIA = OUT / "static" / "media"
DATA.mkdir(parents=True, exist_ok=True)
MEDIA.mkdir(parents=True, exist_ok=True)

MEDIA_RE = re.compile(r"https://media-production\.lp-cdn\.com/media/([A-Za-z0-9-]+)")
needed = {}  # media id -> alt text (for reporting only)


# ---------------------------------------------------------------- helpers
def cf_decode(hexstr):
    key = int(hexstr[:2], 16)
    return "".join(chr(int(hexstr[i:i + 2], 16) ^ key) for i in range(2, len(hexstr), 2))


def prep(path):
    """Read a page, decode Cloudflare-obfuscated emails, drop scripts/styles."""
    s = path.read_text(encoding="utf-8", errors="ignore")
    s = re.sub(r'<span class="__cf_email__" data-cfemail="([0-9a-f]+)">[^<]*</span>',
               lambda m: cf_decode(m.group(1)), s)
    s = re.sub(r'href="(?:https?://exoduscapitalcre\.com)?/cdn-cgi/l/email-protection#([0-9a-f]+)"',
               lambda m: 'href="mailto:%s"' % cf_decode(m.group(1)), s)
    s = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", s, flags=re.S)
    return s


def use(url, alt=""):
    """Register a Luxury Presence media URL; return a placeholder token."""
    m = MEDIA_RE.search(html.unescape(url))
    if not m:
        return url
    needed.setdefault(m.group(1), alt)
    return "{{media:%s}}" % m.group(1)


def text(x):
    x = re.sub(r"<[^>]+>", " ", x or "")
    return re.sub(r"\s+", " ", html.unescape(x)).strip()


def grab(pat, s, flags=re.S, default=""):
    m = re.search(pat, s, flags)
    return m.group(1) if m else default


def balanced(s, start, open_tag="<div", close_tag="</div>"):
    """Return inner HTML of the element whose opening tag begins at `start`."""
    i = s.find(">", start) + 1
    depth, j = 1, i
    while depth:
        a = s.find(open_tag, j)
        b = s.find(close_tag, j)
        if b < 0:
            return s[i:]
        if a != -1 and a < b:
            depth += 1
            j = a + len(open_tag)
        else:
            depth -= 1
            j = b + len(close_tag)
    return s[i:b]


def meta(s, name):
    v = html.unescape(grab(r'<meta (?:name|property)="%s" content="([^"]*)"' % re.escape(name), s))
    return "" if v in ("null", "undefined") else v


def localize_html(frag):
    """Rewrite a rich-text fragment: local media, relative internal links, no srcset."""
    frag = re.sub(r'\s(?:srcset|sizes|loading|width|height)="[^"]*"', "", frag)
    frag = re.sub(r'src="([^"]+)"', lambda m: 'src="%s"' % use(m.group(1)), frag)
    frag = frag.replace('href="https://exoduscapitalcre.com/', 'href="/')
    frag = frag.replace('href="https://exoduscapitalcre.com"', 'href="/"')
    frag = re.sub(r'\s(?:class|id|style|data-[a-z-]+)="[^"]*"', "", frag)
    frag = re.sub(r"\n\s*\n+", "\n", frag)
    return frag.strip()


# ---------------------------------------------------------------- properties
def extract_properties():
    # list pages paginate (9 per page); the snapshot may hold several pages per list
    def links(pattern):
        out = []
        for f in sorted(SRC.glob(pattern), key=lambda f: (len(f.name), f.name)):
            out += re.findall(r'href="/properties/([^"]+)"', prep(f))
        return [x for x in out if x != "track-record"]
    order_sold = links("properties_track-record*.html")
    order_active = links("listings*.html")
    order_sold = list(dict.fromkeys(order_sold))
    order_active = list(dict.fromkeys(order_active))
    props = []
    for f in sorted((SRC / "properties").glob("*.html")):
        slug = f.stem
        s = prep(f)
        intro_i = s.find('class="redesign property-intro-2"')
        if intro_i < 0:
            print("  !! no intro on", slug)
            continue
        intro = s[intro_i:s.find("</section>", intro_i)]
        images = []
        for tag in re.findall(r"<img [^>]+>", intro):
            src = grab(r'src="([^"]+)"', tag)
            alt = html.unescape(grab(r'alt="([^"]*)"', tag))
            images.append({"src": use(src, alt), "alt": alt})
        p = {
            "slug": slug,
            "status": text(grab(r'<span class="label">(.*?)</span>', intro)),
            "title": text(grab(r"<h1[^>]*>(.*?)</h1>", intro)),
            "location": text(grab(r'<p class="feature">(.*?)</p>', intro)),
            "price": text(grab(r"<h5>(.*?)</h5>", intro)),
            "images": images,
            "lat": grab(r'data-lat="([^"]*)"', s) or None,
            "lng": grab(r'data-lng="([^"]*)"', s) or None,
            "schedule_tour": "js-scheduled-form" in s,
            "meta_title": html.unescape(grab(r"<title>(.*?)</title>", s)),
            "meta_description": meta(s, "description"),
        }
        # Active listings come from the /listings page; everything else is a
        # closed deal shown on the track record, ordered by price (high to low),
        # which is how Luxury Presence sorted it. Set "hidden": true by hand in
        # properties.json to keep a page but drop it from every list.
        price_num = int(re.sub(r"[^0-9]", "", p["price"]) or 0)
        if slug in order_active:
            p["section"], p["order"] = "listings", order_active.index(slug)
        else:
            p["section"], p["order"] = "track-record", -price_num
        p["hidden"] = False
        # anything unexpected on the page?
        comps = re.findall(r'<section\b[^>]*>\s*<div\s+class="([^"]*)"', s)
        extra = [c for c in comps if not any(k in c for k in ("property-intro-2", "schedule", "wrapper", "feed", "double-image-grid"))]
        if extra:
            print("  ?? extra components on", slug, extra)
        props.append(p)
    props.sort(key=lambda p: (p["section"], p["order"]))
    return props


# ---------------------------------------------------------------- agents
def extract_agents():
    agents = []
    team = prep(SRC / "team.html")
    order = list(dict.fromkeys(re.findall(r'href="/agent/([^"]+)"', team)))
    for f in sorted((SRC / "agents").glob("*.html")):
        slug = f.stem
        s = prep(f)
        hdr_i = s.find('<section class="agent-content__header">')
        hdr = s[hdr_i:s.find("</section>", hdr_i)]
        photo_tag = grab(r"(<img [^>]+>)", hdr)
        body_i = s.find('<section class="agent-content__body">')
        body = s[body_i:s.find("</section>", body_i)]
        bio_i = body.find('class="agent-content__body__bio"')
        bio = balanced(body, body.rfind("<div", 0, bio_i)) if bio_i >= 0 else ""
        bio = re.sub(r"<h3>.*?</h3>", "", bio, count=1, flags=re.S)
        socials = []
        for href, label in re.findall(r'<a href="([^"]+)" target="_blank"><span class="socials__link[^"]*"><i[^>]*></i></span><span class="link">([^<]*)</span>', body):
            socials.append({"label": label.strip(), "url": href})
        press = []
        for m in re.finditer(r'<a href="([^"]+)" class="f-press__item"[^>]*>(.*?)</a>', s, re.S):
            href, inner = m.group(1), m.group(2)
            press.append({
                "url": html.unescape(href),
                "image": use(grab(r'src="([^"]+)"', inner)),
                "title": text(grab(r'f-press__item-title">(.*?)</h4>', inner)),
                "description": text(grab(r'f-press__item-description">(.*?)</div>', inner)),
                "source": text(grab(r'f-press__item-info">(.*?)<span>', inner)),
                "date": text(grab(r"</span>(.*?)</div>", grab(r'(f-press__item-info">.*?</div>)', inner))),
            })
        a = {
            "slug": slug,
            "name": text(grab(r'<h2 class="lp-h2">(.*?)</h2>', hdr)),
            "role": text(grab(r'<p class="position">(.*?)</p>', hdr)),
            "email": grab(r'href="mailto:([^"]+)"', hdr),
            "phone": text(grab(r'href="tel:[^"]*">(.*?)</a>', hdr)),
            "photo": use(grab(r'src="([^"]+)"', photo_tag)),
            "photo_alt": html.unescape(grab(r'alt="([^"]*)"', photo_tag)),
            "headline": text(grab(r'image-page-introduction.*?<h1[^>]*>(.*?)</h1>', s)),
            "socials": socials,
            "bio_html": localize_html(bio),
            "press": press,
            "meta_title": html.unescape(grab(r"<title>(.*?)</title>", s)),
            "meta_description": meta(s, "description"),
            "order": order.index(slug) if slug in order else 99,
            # "listed": shown in the grid on /team. Agents with a profile page
            # but no card on the team page (as on the old site) keep listed=false.
            "listed": slug in order,
        }
        agents.append(a)
    agents.sort(key=lambda a: a["order"])
    return agents


# ---------------------------------------------------------------- blog
def extract_blog(dates):
    posts = []
    for f in sorted((SRC / "blog").glob("*.html")):
        slug = f.stem
        s = prep(f)
        intro_i = s.find('class="redesign blog-details-intro"')
        intro = s[intro_i:s.find("</section>", intro_i)]
        hero_tag = grab(r"(<img [^>]+>)", intro)
        content_i = s.find('class="redesign blog-content"')
        box_i = s.find('<div class="intro-box">', content_i)
        body = balanced(s, box_i)
        body = re.sub(r'<ul class="socials.*?</ul>', "", body, flags=re.S)
        posts.append({
            "slug": slug,
            "title": text(grab(r"<h1[^>]*>(.*?)</h1>", intro)),
            "date": dates.get(slug, ""),
            "image": use(grab(r'src="([^"]+)"', hero_tag)),
            "image_alt": html.unescape(grab(r'alt="([^"]*)"', hero_tag)),
            "excerpt": meta(s, "description"),
            "meta_title": html.unescape(grab(r"<title>(.*?)</title>", s)),
            "body_html": localize_html(body),
        })
    return posts


# ---------------------------------------------------------------- testimonials
def extract_testimonials():
    s = prep(SRC / "testimonials.html")
    items = []
    for m in re.finditer(r'<div class="testimonials__item">', s):
        block = balanced(s, m.start())
        full = (grab(r'testimonials__item-full">(.*?)</p>', block)
                or grab(r'testimonials__item-short">(.*?)</p>', block)
                or grab(r'testimonials-list__item-content">\s*<p[^>]*>(.*?)</p>', block)   # short reviews with no expand link
                or grab(r'<p[^>]*>(.*?)</p>', block))
        items.append({
            "name": text(grab(r'author__name[^"]*">(.*?)</h2>', block)),
            "title": text(grab(r'author__position[^"]*">(.*?)</(?:p|span|h3|div)>', block)),
            "quote": text(full),
        })
    return items


# ---------------------------------------------------------------- privacy policy
def extract_privacy():
    s = prep(SRC / "terms-and-conditions.html")
    body = s[s.find("<body"):]
    best = ""
    for m in re.finditer(r"<section\b", body):
        seg = body[m.start():body.find("</section>", m.start())]
        if len(text(seg)) > len(text(best)):
            best = seg
    inner = best[best.find("</h1>") + 5:] if "</h1>" in best else best
    inner = re.sub(r'\s(?:class|id|style|data-[a-z-]+)="[^"]*"', "", inner)
    inner = re.sub(r"</?(?:div|section)[^>]*>", "", inner)
    return re.sub(r"\n\s*\n+", "\n", inner).strip() + "\n"


# ---------------------------------------------------------------- site-wide assets
SITE_ASSETS = {
    "logo_dark": "imysmjealn9glmmqrkr7",       # dark logo on light backgrounds
    "logo_light": "p8nszmj4ouvdopuwwu0h",      # white logo on dark backgrounds
    "x_mark": "87715065-3533-4a55-bf49-305fc2cca4d1",
    "press": ["krzikvyes5egtvuxugim", "ewlu9bqhzushhalfv0gh", "itk4zafdkyhw62uyoako", "clynm0totmrk8poh4w7o",
              "fkfmrnpc45olimozjaj2", "t0gncin7jpjfwvxj2mme", "ahon893al3alkfh1sorg"],
    "submarkets": ["qogqtlhwfznnsmm1wgpv", "jprotg4f15vkc4bzy2xc", "dh4ybr0j7boqleimpths", "yrdnruhavnubk6zr6t0y",
                   "tjownvy8z1o6jnpqv1u6", "q4mixsek2yklsn7b31ey", "ojaiwl26ffuqkuwrkcaw", "vfbp7qzqrxdu7kio9nie",
                   "rsrffwb0xbbm1vfzzobj", "n5t5kpy082hrv8zpgcxg", "zwuzjunptdldzmpnlpwk", "k3n3webc9bor6qznlm1w",
                   "div4v7x6ti6bmk0zielr"],
    "stats_bg": "d9008ba2-193e-4251-b96f-f38ca9d2ef7b",
    "cta_contact": "1d414250-2f8f-4ad5-8122-b34e7e5fe66d",
    "cta_updates": "6c0393d7-b8cc-4c62-956c-5eada9e52f0b",
    "team_hero": "vhbjyueunb9kdlqpschk",
    "founder_poster": "3dca8e58-22e0-4b2f-a22b-06895469e3e2",
    "careers_team": "235d0d96-f7e6-430d-a21d-20e5a6722f27",
    "careers_culture": ["01c49dcc-932d-4765-9d82-d8fc602d2041", "84b52548-e02b-412c-b6a8-79337e7094e0"],
    "partner_logo": "c42cbc91-8ce2-4d21-b99c-94b8099851aa",
    "partner_press": ["lx848cijxhweyub3lmzw", "mjpz3oyhqtzkwpfesxeg", "ku6jor9tlqzzjp9rmgjs", "gaop6r27odhz6lkebavk",
                      "ctdvc2mbog8k7pgjfvjn", "so6fweqtcdgbp2fghqwr"],
    "partner_grid": ["46681eb1-028e-476c-9251-614f69c45a6f", "d5504827-1591-42f7-aced-a014a2c6c955", "e254baa7-6e84-4568-99b6-1ea8afc57678"],
    "news": {
        "womlead": "e13nwo9tndlhzbhlr78y", "usreporter": "g6rxz8p0otxw3ytyk6em", "realdeal": "cirik4cqjr1ni0maa68p",
        "nyt_81st": "y3vzp1hltmdft3tas9z6", "nyt_middagh": "wpbsiaxfoypz9dzzx09c", "nyrej": "fpwmydjxwuibcenjizlj",
        "commercial_observer": "g1yd6tolrk9gms9ty7qq",
    },
}

VIDEOS = {
    # name: (mp4 url, poster url)
    "hero-home": ("https://res.cloudinary.com/luxuryp/videos/f_mp4,vc_h264,w_1280,c_limit/hqjroypkne2smizrib9h/website-new-faces-v1-1.mp4",
                  "https://res.cloudinary.com/luxuryp/videos/f_jpg,q_auto/so_0,eo_0/hqjroypkne2smizrib9h/website-new-faces-v1-1.jpg"),
    "reviews-bg": ("https://res.cloudinary.com/luxuryp/video/upload/f_mp4,vc_h264,w_1280,c_limit/v1649623232/glfgstjontqapek10oaw.mp4",
                   "https://res.cloudinary.com/luxuryp/video/upload/f_jpg,q_auto/so_0,eo_0/v1649623232/glfgstjontqapek10oaw.jpg"),
    "transactions-bg": ("https://res.cloudinary.com/luxuryp/video/upload/f_mp4,vc_h264,w_1280,c_limit/v1632176846/gvpvzsb3bpy5pe0qs5ho.mp4",
                        "https://res.cloudinary.com/luxuryp/video/upload/f_jpg,q_auto/so_0,eo_0/v1632176846/gvpvzsb3bpy5pe0qs5ho.jpg"),
    "hero-vision": ("https://res.cloudinary.com/luxuryp/video/upload/f_mp4,vc_h264,w_1280,c_limit/v1652454713/mvilbzmukwv5c0rxlf5y.mp4",
                    "https://res.cloudinary.com/luxuryp/video/upload/f_jpg,q_auto/so_0,eo_0/v1652454713/mvilbzmukwv5c0rxlf5y.jpg"),
    "hero-partnership": ("https://res.cloudinary.com/luxuryp/video/upload/f_mp4,vc_h264,w_1280,c_limit/v1652457006/osrc7f2j6fezqbm8sxf4.mp4",
                         "https://res.cloudinary.com/luxuryp/video/upload/f_jpg,q_auto/so_0,eo_0/v1652457006/osrc7f2j6fezqbm8sxf4.jpg"),
}


def walk_assets(node):
    if isinstance(node, str):
        return use("https://media-production.lp-cdn.com/media/" + node)
    if isinstance(node, list):
        return [walk_assets(n) for n in node]
    if isinstance(node, dict):
        return {k: walk_assets(v) for k, v in node.items()}
    return node


# ---------------------------------------------------------------- download
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
       "image/svg+xml": ".svg", "image/avif": ".avif", "video/mp4": ".mp4"}


def existing(mid):
    hits = list(MEDIA.glob(mid + ".*"))
    return hits[0].name if hits else None


def download_one(mid):
    name = existing(mid)
    if name:
        return mid, name
    tmp = MEDIA / (mid + ".tmp")
    subprocess.run(["curl", "-sL", "-A", "Mozilla/5.0", "https://media-production.lp-cdn.com/media/" + mid, "-o", str(tmp)], check=True)
    mime = subprocess.run(["file", "--mime-type", "-b", str(tmp)], capture_output=True, text=True).stdout.strip()
    ext = EXT.get(mime, "")
    if not ext:
        print("  !! unknown mime", mime, "for", mid)
        ext = ".bin"
    final = MEDIA / (mid + ext)
    tmp.rename(final)
    return mid, final.name


def download_videos():
    out = {}
    for name, (mp4, poster) in VIDEOS.items():
        for url, ext in ((mp4, ".mp4"), (poster, ".jpg")):
            dest = MEDIA / (name + ext)
            if not dest.exists():
                subprocess.run(["curl", "-sL", "-A", "Mozilla/5.0", url, "-o", str(dest)], check=True)
            out.setdefault(name, {})["video" if ext == ".mp4" else "poster"] = "/media/" + dest.name
    return out


# ---------------------------------------------------------------- main
def main():
    # blog dates: the blog index (M/D/YY) is the source of truth; the sitemap's
    # lastmod (YYYY-MM-DD) fills in anything the index did not show.
    dates = {}
    for fname in ("blog-lastmod.json", "blog-dates.json"):
        f = SRC / fname
        if f.exists():
            dates.update(json.loads(f.read_text()))

    print("properties..."); properties = extract_properties()
    print("agents...");     agents = extract_agents()
    print("blog...");       posts = extract_blog(dates)
    print("testimonials..."); testimonials = extract_testimonials()
    print("privacy...");      (DATA / "privacy.html").write_text(extract_privacy())
    assets = walk_assets(SITE_ASSETS)

    print("downloading %d media files..." % len(needed))
    with ThreadPoolExecutor(8) as ex:
        names = dict(ex.map(download_one, sorted(needed)))
    print("downloading videos...")
    assets["videos"] = download_videos()

    def resolve(obj):
        s = json.dumps(obj, indent=2, ensure_ascii=False)
        s = re.sub(r"\{\{media:([A-Za-z0-9-]+)\}\}", lambda m: "/media/" + names[m.group(1)], s)
        return s

    (DATA / "properties.json").write_text(resolve(properties) + "\n")
    (DATA / "team.json").write_text(resolve(agents) + "\n")
    (DATA / "blog.json").write_text(resolve(posts) + "\n")
    (DATA / "testimonials.json").write_text(resolve(testimonials) + "\n")
    (DATA / "assets.json").write_text(resolve(assets) + "\n")
    print("done: %d properties, %d agents, %d posts, %d testimonials" % (len(properties), len(agents), len(posts), len(testimonials)))


if __name__ == "__main__":
    main()
