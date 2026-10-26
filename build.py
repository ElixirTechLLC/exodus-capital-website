#!/usr/bin/env python3
"""
Build the Exodus Capital website.

    python3 build.py            -> writes the finished site into dist/

Everything editable lives in data/ (JSON + the privacy policy HTML) and
static/ (stylesheet, script, images). This file holds the page templates.
Python 3.9+ standard library only.
"""
import datetime, html, json, pathlib, re, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent
DATA, STATIC, DIST = ROOT / "data", ROOT / "static", ROOT / "dist"

# `python3 build.py --flat` writes a portable copy to dist-flat/: every page is a
# single file in one folder (team.html, properties-191-bond-street.html, ...)
# and every link is relative, so it can be previewed from any static host or
# folder without a web server configured for clean URLs. Forms do not post there.
FLAT = "--flat" in sys.argv
if FLAT:
    DIST = ROOT / "dist-flat"


def _opt(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


# `python3 build.py --base /repo-name --out docs` builds for a host that serves
# the site under a sub-path (GitHub Pages project sites). Every absolute link
# gets the prefix. Forms cannot post on such a host.
BASE = _opt("--base", "").rstrip("/")
if "--out" in sys.argv:
    DIST = ROOT / _opt("--out", "dist")


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


site = load("site.json")
assets = load("assets.json")
properties = [p for p in load("properties.json") if not p.get("hidden")]
team = load("team.json")
posts = load("blog.json")
testimonials = load("testimonials.json")
privacy_html = (DATA / "privacy.html").read_text(encoding="utf-8")

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def asset_version(name):
    """Short content hash so browsers and CDNs refetch changed CSS/JS."""
    import hashlib
    return hashlib.md5((STATIC / "assets" / name).read_bytes()).hexdigest()[:8]


CSS_V, JS_V = asset_version("site.css"), asset_version("site.js")
POSTS_PER_PAGE = 8


# ---------------------------------------------------------------- small helpers
def parse_date(d):
    """'10/15/26' or '2026-10-15' -> datetime.date (None if unknown)."""
    for fmt in ("%m/%d/%y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(d.strip(), fmt).date()
        except (ValueError, AttributeError):
            pass
    return None


def nice_date(d):
    dt = parse_date(d)
    return dt.strftime("%B %-d, %Y") if dt else d


for p in posts:
    p["_date"] = parse_date(p["date"]) or datetime.date(2000, 1, 1)
posts.sort(key=lambda p: p["_date"], reverse=True)
listings = [p for p in properties if p["section"] == "listings"]
sold = [p for p in properties if p["section"] == "track-record"]


def write(path, content):
    out = DIST / path.lstrip("/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


def page_path(url):
    """'/team/' -> 'team/index.html'  (flat mode: 'team.html')"""
    core = url.strip("/")
    if FLAT:
        return (core.replace("/", "-") + ".html") if core else "index.html"
    return (core + "/index.html") if core else "index.html"


def prefix_links(doc):
    """Prefix every root-relative link with BASE (sub-path hosting)."""
    doc = re.sub(r'\b(href|src|poster|data-src|action)="/(?!/)([^"]*)"',
                 lambda m: '%s="%s/%s"' % (m.group(1), BASE, m.group(2)), doc)
    doc = re.sub(r"url\(/(media/[^)]+)\)", lambda m: "url(%s/%s)" % (BASE, m.group(1)), doc)
    return doc


def postprocess(doc):
    if FLAT:
        return flatten_links(doc)
    if BASE:
        return prefix_links(doc)
    return doc


def flatten_links(doc):
    """Rewrite absolute site links in a finished page to flat, relative ones."""
    doc = re.sub(r'\b(href|src|poster|data-src|action)="/([^"#?]*)([#?][^"]*)?"', _attr, doc)
    doc = re.sub(r"url\(/(media/[^)]+)\)", r"url(\1)", doc)
    return doc


def _attr(m):
    name, path, rest = m.group(1), m.group(2), m.group(3) or ""
    if path.startswith("/"):                   # protocol-relative URL, leave alone
        return m.group(0)
    if path == "" and rest.startswith("#"):
        return '%s="%s"' % (name, rest)
    if path.startswith(("assets/", "media/")) or "." in path.rsplit("/", 1)[-1]:
        return '%s="%s%s"' % (name, path, rest)      # a real file (css, image, favicon)
    if name == "action":
        return '%s="%s"' % (name, "#")           # no form backend on a flat preview
    return '%s="%s%s"' % (name, page_path("/" + path), rest)


# ---------------------------------------------------------------- icons
ICONS = {
    "envelope": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="3" y="5" width="18" height="14" rx="1"/><path d="M3 7l9 6 9-6"/></svg>',
    "phone": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.3"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a1 1 0 01-1 1A16 16 0 014 5a1 1 0 011-1z"/></svg>',
    "fax": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="4" y="9" width="16" height="11" rx="1"/><path d="M8 9V4h8v5M8 14h8M8 17h5"/></svg>',
    "pin": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.3"><path d="M12 21s-6-5.5-6-11a6 6 0 0112 0c0 5.5-6 11-6 11z"/><circle cx="12" cy="10" r="2.2"/></svg>',
    "linkedin": '<svg viewBox="0 0 24 24"><path d="M6.5 8.5h-3V20h3V8.5zM5 4a1.8 1.8 0 100 3.6A1.8 1.8 0 005 4zm15 9.1c0-3.2-1.7-4.8-4.1-4.8-1.9 0-2.8 1-3.3 1.8V8.5H9.6V20h3.1v-6.2c0-1.6.3-3.2 2.3-3.2s2 1.9 2 3.3V20H20v-6.9z"/></svg>',
    "instagram": '<svg viewBox="0 0 24 24"><path d="M12 3c2.4 0 2.7 0 3.7.1 2.5.1 3.9 1.4 4.1 4.1.1 1 .1 1.3.1 3.7s0 2.7-.1 3.7c-.1 2.7-1.5 4-4.1 4.1-1 .1-1.3.1-3.7.1s-2.7 0-3.7-.1c-2.7-.1-4-1.5-4.1-4.1C4 14.7 4 14.4 4 12s0-2.7.1-3.7C4.2 5.6 5.6 4.2 8.3 4.1 9.3 4 9.6 3 12 3zm0 2c-2.4 0-2.6 0-3.6.1-1.9.1-2.8 1-2.9 2.9C5.4 9 5.4 9.3 5.4 12s0 2.6.1 3.6c.1 1.9 1 2.8 2.9 2.9 1 .1 1.2.1 3.6.1s2.6 0 3.6-.1c1.9-.1 2.8-1 2.9-2.9.1-1 .1-1.2.1-3.6s0-2.6-.1-3.6c-.1-1.9-1-2.8-2.9-2.9C14.6 5 14.4 5 12 5zm0 3.4a3.6 3.6 0 110 7.2 3.6 3.6 0 010-7.2zm0 1.9a1.7 1.7 0 100 3.4 1.7 1.7 0 000-3.4zm3.9-2.5a.9.9 0 110 1.8.9.9 0 010-1.8z"/></svg>',
    "facebook": '<svg viewBox="0 0 24 24"><path d="M13.5 21v-7h2.4l.4-3h-2.8V9.1c0-.9.3-1.5 1.5-1.5h1.5V5c-.3 0-1.2-.1-2.2-.1-2.2 0-3.7 1.3-3.7 3.8V11H8v3h2.6v7h2.9z"/></svg>',
    "x": '<svg viewBox="0 0 24 24"><path d="M17.5 3h3l-7 8 8.2 10h-6.4l-5-6.5L4.6 21h-3l7.5-8.6L1.3 3h6.6l4.5 6L17.5 3zm-1.1 16.2h1.7L7 4.7H5.1l11.3 14.5z"/></svg>',
    "left": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M15 5l-7 7 7 7"/></svg>',
    "right": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 5l7 7-7 7"/></svg>',
    "down2": '<svg viewBox="0 0 32 32" fill="currentColor"><path d="M22.3 15.3L16 21.5l-6.3-6.2a1 1 0 00-1.4 1.4l7 6.9a1 1 0 001.4 0l7-6.9a1 1 0 00-1.4-1.4z"/><path d="M15.3 16.7a1 1 0 001.4 0l7-6.9a1 1 0 00-1.4-1.4L16 14.5 9.7 8.3a1 1 0 00-1.4 1.4l7 7z"/></svg>',
    "play": '<svg viewBox="0 0 24 24"><path d="M7 4l13 8-13 8z"/></svg>',
}


def icon(name):
    return ICONS[name]


def social_links(links, cls="social-icon"):
    out = []
    for key, url in links.items():
        if url:
            out.append('<a class="%s" href="%s" target="_blank" rel="noopener" aria-label="%s">%s</a>' % (cls, E(url), key.title(), icon(key)))
    return "".join(out)


# ---------------------------------------------------------------- shared chrome
def nav_link(item, cls="header__link"):
    if item.get("modal"):
        return '<button class="%s" data-modal="%s">%s</button>' % (cls, E(item["modal"]), E(item["label"]))
    return '<a class="%s" href="%s">%s</a>' % (cls, E(item["href"]), E(item["label"]))


def header():
    return '''
<header class="header">
  <div class="header__inner">
    <nav class="header__nav header__nav--left" aria-label="Primary">%s</nav>
    <a class="header__logo" href="/" aria-label="%s home">
      <img class="logo--light" src="%s" alt="%s" width="170" height="52">
      <img class="logo--dark" src="%s" alt="%s" width="170" height="52">
    </a>
    <nav class="header__nav header__nav--right" aria-label="Secondary">%s
      <button class="hamburger" data-open-drawer aria-label="Open menu"><span></span></button>
    </nav>
  </div>
</header>''' % ("".join(nav_link(i) for i in site["nav_left"]), E(site["name"]),
                 E(assets["logo_light"]), E(site["name"]), E(assets["logo_dark"]), E(site["name"]),
                 "".join(nav_link(i) for i in site["nav_right"]))


def drawer():
    items = "".join("<li>%s</li>" % nav_link(i, cls="drawer__link") for i in site["menu"])
    return '''
<div class="drawer" aria-hidden="true">
  <div class="drawer__backdrop" data-close-drawer></div>
  <nav class="drawer__panel" aria-label="Menu">
    <button class="drawer__close" data-close-drawer aria-label="Close menu">&times;</button>
    <ul class="drawer__nav">%s</ul>
    <div class="drawer__contact">
      <a href="mailto:%s">%s</a>
      <a href="tel:%s">%s</a>
      <p>%s<br>%s</p>
      <div class="drawer__social">%s</div>
    </div>
  </nav>
</div>''' % (items, E(site["email"]), E(site["email"]), E(site["phone"].replace("-", "")), E(site["phone"]),
             E(site["address"][0]), E(site["address"][1]), social_links(site["social"]))


def footer():
    lic = site["footer_license"]
    cells = [
        ("envelope", "Email", '<a href="mailto:%s">%s</a>' % (E(site["email"]), E(site["email"]))),
        ("phone", "Phone Number", '<a href="tel:%s">%s</a>' % (E(site["phone"].replace("-", "")), E(site["phone"]))),
        ("fax", site["phone2_label"], '<a href="tel:%s">%s</a>' % (E(site["phone2"].replace("-", "")), E(site["phone2"]))),
        ("pin", "Address", "%s<br>%s" % (E(site["address"][0]), E(site["address"][1]))),
    ]
    cells_html = "".join('<div class="footer__cell">%s<div><div class="footer__cell-title">%s</div><div class="footer__cell-value">%s</div></div></div>' % (icon(i), E(t), v) for i, t, v in cells)
    disclaimer = "".join("<p>%s</p>" % E(d) for d in site["footer_disclaimer"])
    return '''
<footer class="footer">
  <img class="footer__mark" src="%s" alt="">
  <div class="container">
    <h3 class="footer__name">%s</h3>
    <div class="footer__info">%s</div>
    <div class="footer__legal">
      %s
      <p>&nbsp;</p>
      <p>%s</p>
      <p>%s<br>E: <a href="mailto:%s">%s</a><br>P: <a href="tel:%s">%s</a></p>
    </div>
    <div class="footer__bottom">
      <div>Copyright &copy; <span data-year>%d</span> | <a href="/terms-and-conditions/">Privacy Policy</a> | <a href="/sitemap/">Sitemap</a></div>
      <div class="footer__socials">%s</div>
    </div>
  </div>
</footer>''' % (E(assets["x_mark"]), E(site["name"]), cells_html, disclaimer, E(lic["line"]), E(lic["license"]),
                E(lic["email"]), E(lic["email"]), E(re.sub(r"[^0-9]", "", lic["phone"])), E(lic["phone"]),
                datetime.date.today().year, social_links(site["social"]))


def mobile_contact():
    return '<div class="mobile-contact"><a href="mailto:%s" aria-label="Email">%s</a><a href="tel:%s" aria-label="Call">%s</a></div>' % (
        E(site["email"]), icon("envelope"), E(site["phone_mobile_button"].replace("-", "")), icon("phone"))


# ---------------------------------------------------------------- forms
def form_open(name, cls="form"):
    f = site["forms"]
    if f.get("provider") == "netlify":
        attrs = 'name="%s" method="POST" action="/" data-ajax data-provider="netlify" data-netlify="true" netlify-honeypot="company"' % E(name)
        hidden = '<input type="hidden" name="form-name" value="%s">' % E(name)
    else:
        attrs = 'name="%s" method="POST" action="%s" data-ajax data-provider="custom"' % (E(name), E(f.get("action", "")))
        hidden = '<input type="hidden" name="form" value="%s">' % E(name)
    return '<form class="%s" %s data-success="Message sent successfully!">%s<p class="honeypot"><label>Company <input name="company" tabindex="-1" autocomplete="off"></label></p>' % (cls, attrs, hidden)


def consent(id_):
    return '<label class="form__consent"><input type="checkbox" name="consent" value="yes" required id="%s"><span>Opt In/Disclaimer Consent: %s <a href="/terms-and-conditions/">Privacy Policy</a>.</span></label>' % (id_, E(site["consent_text"]))


def contact_form(dark=False, id_="contact"):
    return form_open("contact", "form form--dark" if dark else "form") + '''
  <div class="form__row">
    <input type="text" name="name" placeholder="Name" required aria-label="Name">
    <input type="email" name="email" placeholder="Email" required aria-label="Email">
  </div>
  <input type="tel" name="phone" placeholder="Phone" aria-label="Phone">
  <textarea name="message" placeholder="Message" aria-label="Message"></textarea>
  %s
  <div><button class="btn %s" type="submit">Submit</button></div>
  <p class="form__status" aria-live="polite"></p>
</form>''' % (consent(id_ + "-consent"), "btn--light" if dark else "btn--solid-dark")


def register_form():
    return form_open("market-updates") + '''
  <input type="email" name="email" placeholder="Email" required aria-label="Email">
  <input type="tel" name="phone" placeholder="Phone Number" aria-label="Phone Number">
  <select name="interest" aria-label="Interested in" required>
    <option value="" disabled selected>Interested in...</option>
    <option>Selling &amp; Buying</option><option>Selling</option><option>Buying</option><option>Renting</option><option>Other</option>
  </select>
  %s
  <div><button class="btn btn--solid-dark" type="submit">Submit</button></div>
  <p class="form__status" aria-live="polite"></p>
</form>''' % consent("register-consent")


def modals():
    cells = [("phone", "Phone", '<a href="tel:%s">%s</a>' % (E(site["phone"].replace("-", "")), E(site["phone"]))),
             ("envelope", "Email", '<a href="mailto:%s">%s</a>' % (E(site["email"]), E(site["email"]))),
             ("fax", site["phone2_label"].replace(" Number", ""), '<a href="tel:%s">%s</a>' % (E(site["phone2"].replace("-", "")), E(site["phone2"]))),
             ("pin", "Address", "%s<br>%s" % (E(site["address"][0]), E(site["address"][1])))]
    cells_html = "".join('<div class="contact-cell">%s<div><span>%s</span>%s</div></div>' % (icon(i), E(t), v) for i, t, v in cells)
    return '''
<div class="modal" id="modal-contact" role="dialog" aria-modal="true" aria-label="Contact Us">
  <div class="modal__backdrop" data-close-modal></div>
  <div class="modal__box">
    <aside class="modal__aside"><button class="modal__close" data-close-modal aria-label="Close">&times;</button><h2>Contact Details</h2>%s</aside>
    <div class="modal__main"><h2>Submit a Message</h2>%s</div>
  </div>
</div>
<div class="modal" id="modal-register" role="dialog" aria-modal="true" aria-label="Receive Market Updates">
  <div class="modal__backdrop" data-close-modal></div>
  <div class="modal__box modal__box--single">
    <button class="modal__close" data-close-modal aria-label="Close">&times;</button>
    <div class="modal__main"><h2>Receive Market Updates</h2>%s</div>
  </div>
</div>
<div class="modal video-modal" id="modal-video" role="dialog" aria-modal="true" aria-label="Video">
  <div class="modal__backdrop" data-close-modal></div>
  <div class="modal__box modal__box--single">
    <button class="modal__close" data-close-modal aria-label="Close" style="color:#fff">&times;</button>
    <iframe data-src title="Video" allow="autoplay; encrypted-media" allowfullscreen></iframe>
  </div>
</div>''' % (cells_html, contact_form(id_="modal-contact"), register_form())


# ---------------------------------------------------------------- layout
def layout(title, description, body, path, header_light=False, og_image=None, body_class=""):
    classes = " ".join(c for c in [("header-light" if header_light else ""), body_class] if c)
    og = og_image or assets["cta_contact"]
    return '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<meta name="description" content="%s">
<link rel="canonical" href="%s">
<meta property="og:type" content="website">
<meta property="og:site_name" content="%s">
<meta property="og:title" content="%s">
<meta property="og:description" content="%s">
<meta property="og:image" content="%s">
<meta property="og:url" content="%s">
<meta name="theme-color" content="#ffffff">
<link rel="icon" type="image/png" href="/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Aldrich:400|Hind+Guntur:300,400,500,600,700&display=swap">
<link rel="stylesheet" href="/assets/site.css?v=%s">
%s
</head>
<body class="%s">
%s%s
<main>%s</main>
%s%s%s
<script src="/assets/site.js?v=%s" defer></script>
</body>
</html>
''' % (E(title), E(description), E(site["url"] + path), E(site["name"]), E(title), E(description),
       E(site["url"] + og), E(site["url"] + path), CSS_V, site.get("analytics_html", ""), classes,
       header(), drawer(), body, footer(), modals(), mobile_contact(), JS_V)


# ---------------------------------------------------------------- components
def hero_video(video_key, inner, overlay="hero__overlay", extra=""):
    v = assets["videos"][video_key]
    return '''
<section class="hero %s">
  <img class="hero__poster" src="%s" alt="" fetchpriority="high">
  <video class="hero__video" autoplay muted loop playsinline preload="auto" src="%s"></video>
  <div class="%s"></div>
  <div class="hero__content">%s</div>
</section>''' % (extra, E(v["poster"]), E(v["video"]), overlay, inner)


def banner(title, image, tall=False, grayscale=True, pretitle=""):
    return '''
<section class="banner %s">
  <img class="banner__bg" src="%s" alt="" %s>
  <div class="container">%s<h1>%s</h1></div>
</section>''' % ("banner--tall" if tall else "", E(image), "" if grayscale else 'style="filter:none"',
                 ('<span class="pretitle">%s</span>' % E(pretitle)) if pretitle else "", E(title))


def property_card(p, dark=False):
    img = p["images"][0] if p["images"] else {"src": "", "alt": ""}
    return '''
<a class="card" href="/properties/%s/">
  <div class="card__img">
    <img src="%s" alt="%s" loading="lazy">
    <span class="card__label">%s</span>
    <div class="card__hover"><span class="btn btn--light">View Property</span></div>
  </div>
  <div class="card__body">
    <h4 class="card__title">%s</h4>
    <div class="card__loc">%s</div>
    <div class="card__price">%s</div>
  </div>
</a>''' % (E(p["slug"]), E(img["src"]), E(img["alt"] or p["title"]), E(p["status"]), E(p["title"]), E(p["location"]), E(p["price"]))


def property_carousel(title, items, dark=False, show_mark=True, view_all="/properties/track-record/", autoplay=4000):
    cards = "".join('<div class="carousel__item">%s</div>' % property_card(p, dark) for p in items)
    return '''
<section class="section %s">
  <div class="container">
    <div class="carousel" data-carousel data-autoplay="%d">
      %s
      <h2 class="section__title">%s</h2>
      <div class="carousel__head">
        <button class="link-caps" data-prev>previous</button><span class="sep"></span><button class="link-caps" data-next>next</button>
      </div>
      <div class="carousel__track" data-track>%s</div>
      <div class="carousel__foot"><a class="btn %s" href="%s">View All</a></div>
    </div>
  </div>
</section>''' % ("section--dark" if dark else "section--light", autoplay,
                 ('<img class="intro__mark" src="%s" alt="">' % E(assets["x_mark"])) if show_mark else "",
                 E(title), cards, "btn--light" if dark else "btn--dark", E(view_all))


def stats_block(items, title="", bg=True, cols=None):
    cells = "".join('<div><div class="stats__value" data-count="%s">%s</div><div class="stats__label">%s</div></div>' % (E(s["value"]), E(s["value"]), E(s["label"])) for s in items)
    box_cls = "stats__box" + (" stats__box--5" if (cols or len(items)) == 5 else "")
    if bg:
        return '<section class="stats" style="background-image:url(%s)"><div class="container">%s<div class="%s">%s</div></div></section>' % (
            E(assets["stats_bg"]), ('<h2 class="stats__title">%s</h2>' % E(title)) if title else "", box_cls, cells)
    return '<section class="stats stats--plain"><div class="container">%s<div class="%s">%s</div></div></section>' % (
        ('<h2 class="stats__title">%s</h2>' % E(title)) if title else "", box_cls, cells)


def logo_row(images, title="", dark=False, submarkets=False, marquee=False):
    imgs = "".join('<img src="%s" alt="" loading="lazy">' % E(i) for i in images)
    if marquee:
        imgs += imgs  # duplicated so the loop is seamless
    return '''
<section class="section logos %s %s %s %s">
  %s
  <div class="logos__track">%s</div>
</section>''' % ("section--dark" if dark else "section--light", "logos--invert" if dark else "",
                 "logos--submarkets" if submarkets else "", "logos--marquee" if marquee else "",
                 ('<h2 class="logos__title">%s</h2>' % E(title)) if title else "", imgs)


def reviews_section(title):
    v = assets["videos"]["reviews-bg"]
    cards = "".join('''
<div class="review">
  <img class="review__mark" src="%s" alt="">
  <div class="review__name">%s</div>
  <p class="review__text">%s</p>
  <a class="btn btn--light" href="/testimonials/">Read More</a>
</div>''' % (E(assets["x_mark"]), E(t["name"]), E(t["quote"][:230].rsplit(" ", 1)[0] + "...")) for t in testimonials)
    return '''
<section class="reviews section">
  <img class="reviews__poster" src="%s" alt="" loading="lazy">
  <video class="reviews__video" autoplay muted loop playsinline preload="none" data-src="%s"></video>
  <div class="reviews__overlay"></div>
  <div class="container" data-carousel data-autoplay="6000">
    <h2 class="reviews__title">%s</h2>
    <div class="reviews__track" data-track>%s</div>
    <div class="reviews__nav">
      <button class="arrow-btn" data-prev aria-label="Previous">%s</button>
      <button class="arrow-btn" data-next aria-label="Next">%s</button>
    </div>
  </div>
</section>''' % (E(v["poster"]), E(v["video"]), E(title), cards, icon("left"), icon("right"))


def follow_strip(label="Follow Us"):
    handle = site["social"]["instagram"].rstrip("/").rsplit("/", 1)[-1]
    return '''
<section class="follow section--dark">
  <div class="container">
    <span class="pretitle">%s</span>
    <h3><a href="%s" target="_blank" rel="noopener">@%s</a></h3>
    <div class="follow__links">%s</div>
  </div>
</section>''' % (E(label), E(site["social"]["instagram"]), E(handle), social_links(site["social"]))


def cta_grid(left_title=None):
    c = site["cta"]
    return '''
<section class="cta">
  <div class="cta__half" style="background-image:url(%s)"><div><h2>%s</h2><button class="btn btn--light" data-modal="contact">%s</button></div></div>
  <div class="cta__half" style="background-image:url(%s)"><div><h2>%s</h2><button class="btn btn--light" data-modal="register">%s</button></div></div>
</section>''' % (E(assets["cta_contact"]), E(left_title or c["left_title"]), E(c["left_button"]),
                 E(assets["cta_updates"]), E(c["right_title"]), E(c["right_button"]))


def press_grid(items):
    return '<div class="press">' + "".join('''
<a class="press__item" href="%s" target="_blank" rel="noopener">
  <div class="press__img"><img src="%s" alt="%s" loading="lazy"></div>
  <h4 class="press__title">%s</h4>
  %s
  <div class="press__meta">%s &nbsp;|&nbsp; %s</div>
</a>''' % (E(i["url"]), E(i["image"]), E(i["title"]), E(i["title"]),
           ('<div class="press__desc">%s</div>' % E(i["description"])) if i.get("description") else "",
           E(i["source"]), E(i["date"])) for i in items) + "</div>"


def post_card(p):
    return '''
<a class="post-card" href="/blog/%s/">
  <div class="post-card__img"><img src="%s" alt="%s" loading="lazy"></div>
  <h4 class="post-card__title">%s</h4>
  <div class="post-card__date">%s</div>
  <span class="link-caps">Read More</span>
</a>''' % (E(p["slug"]), E(p["image"] or assets["cta_updates"]), E(p["image_alt"] or p["title"]), E(p["title"]), E(nice_date(p["date"])))


# ---------------------------------------------------------------- pages
def page_home():
    h = site["home"]
    hero_inner = '<h1>%s</h1><div class="hero__buttons"><a class="btn btn--light" href="%s">%s</a></div>' % (E(h["hero_title"]), E(h["hero_button"]["href"]), E(h["hero_button"]["label"]))
    body = hero_video("hero-home", hero_inner)
    body += '''
<section class="section section--light intro">
  <div class="container">
    <img class="intro__mark" src="%s" alt="">
    <h2>%s</h2>
    <p class="intro__text">%s</p>
  </div>
</section>''' % (E(assets["x_mark"]), E(h["why_title"]), E(h["why_text"]))
    body += logo_row(assets["press"], dark=True, marquee=True)
    body += stats_block(h["stats"])
    body += logo_row(assets["submarkets"], title=h["submarkets_title"], submarkets=True, marquee=True)
    body += property_carousel(h["transactions_title"], sold[:12])
    body += follow_strip("Follow us")
    body += reviews_section(h["reviews_title"])
    body += cta_grid()
    return layout(site["default_title"].replace("Exodus Capital | ", "Tri State Investment Sales – Transform Assets with Exodus").split(" | ")[0] if False else "Tri State Investment Sales – Transform Assets with Exodus",
                  site["default_description"], body, "/")


def page_team():
    t = site["team"]
    members = "".join('''
<a class="member" href="/agent/%s/">
  <div class="member__img"><img src="%s" alt="%s" loading="lazy"></div>
  <div class="member__name">%s</div>
  <div class="member__role">%s</div>
</a>''' % (E(a["slug"]), E(a["photo"]), E(a["photo_alt"] or a["name"]), E(a["name"]), E(a["role"])) for a in team if a.get("listed", True))
    body = banner(t["hero_title"], assets["team_hero"], tall=True)
    body += '<section class="section section--dark"><div class="container"><h2 class="section__title">%s</h2><div class="team-grid">%s</div></div></section>' % (E(t["grid_title"]), members)
    body += '<section class="section section--light"><div class="container"><h2 class="section__title">%s</h2><p class="section__sub">%s</p>%s</div></section>' % (
        E(t["track_title"]), E(t["track_text"]), stats_block(t["stats"], bg=False).replace('class="stats stats--plain"', 'class="stats stats--plain" style="padding:0"'))
    body += logo_row(assets["press"], title=t["press_title"], marquee=True)
    body += property_carousel(t["notable_title"], sold[:12], show_mark=False)
    body += reviews_section(t["reviews_title"])
    body += follow_strip()
    body += cta_grid()
    return layout("Meet Exodus Capital | New York Investment Firm", "Meet the Exodus Capital team: Tri-State commercial real estate investment sales advisors.", body, "/team/")


def page_agent(a):
    socials = "".join('<li><a href="%s" target="_blank" rel="noopener"><span class="social-icon">%s</span>%s</a></li>' % (E(s["url"]), icon(s["label"].lower()) if s["label"].lower() in ICONS else "", E(s["label"])) for s in a["socials"])
    first = a["name"].split()[0]
    body = banner(a["headline"], assets["team_hero"])
    body += '''
<section class="section section--light">
  <div class="container">
    <div class="agent">
      <div class="agent__photo"><img src="%s" alt="%s"></div>
      <div>
        <h1 class="agent__name">%s</h1>
        <div class="agent__role">%s</div>
        <div class="agent__contact">%s%s</div>
        <p style="margin-top:28px"><button class="btn btn--dark" data-modal="contact">Work with %s</button></p>
      </div>
    </div>
    <div class="agent__bio">
      <div>%s</div>
      <div>%s</div>
    </div>
  </div>
</section>''' % (E(a["photo"]), E(a["photo_alt"] or a["name"]), E(a["name"]), E(a["role"]),
                 ('<a href="mailto:%s">%s</a>' % (E(a["email"]), E(a["email"]))) if a["email"] else "",
                 ('<a href="tel:%s">%s</a>' % (E(re.sub(r"[^0-9]", "", a["phone"])), E(a["phone"]))) if a["phone"] else "",
                 E(first),
                 ('<h3>Social Media</h3><ul class="agent__social">%s</ul>' % socials) if socials else "",
                 ('<h3>About %s</h3>%s' % (E(first), a["bio_html"])) if a["bio_html"] else "")
    if a["press"]:
        body += '<section class="section section--light" style="padding-top:0"><div class="container"><h2 class="section__title">In the News</h2>%s</div></section>' % press_grid(a["press"])
    body += follow_strip()
    body += cta_grid()
    return layout(a["meta_title"] or "%s | %s" % (a["name"], site["name"]), a["meta_description"] or site["default_description"], body, "/agent/%s/" % a["slug"], og_image=a["photo"])


def grid_page(title, items, path, meta_title, meta_desc, extra_top=""):
    cards = "".join(property_card(p) for p in items)
    body = extra_top + '<section class="section section--light" style="padding-top:calc(var(--header-h) + 48px)"><div class="container"><h1 class="sr-only">%s</h1><div class="grid grid--2">%s</div>%s</div></section>' % (
        E(title), cards, "" if items else '<p class="text-center">No listings at the moment. Please check back soon.</p>')
    body += follow_strip() + cta_grid()
    return layout(meta_title, meta_desc, body, path, header_light=True)


def page_listings():
    return grid_page("Our Listings", listings, "/listings/", "Our Listings | New York Real Estate | Exodus Capital",
                     "Current commercial real estate listings from Exodus Capital across the Tri-State area.")


def page_track_record():
    top = '<div style="padding-top:var(--header-h)"></div>' + logo_row(assets["submarkets"], title=site["home"]["submarkets_title"], submarkets=True, marquee=True)
    cards = "".join(property_card(p) for p in sold)
    body = top + '<section class="section section--light" style="padding-top:0"><div class="container"><h1 class="sr-only">Track Record</h1><div class="grid grid--2">%s</div></div></section>' % cards
    body += follow_strip() + cta_grid()
    return layout("Track Record | New York Investment Firm | Exodus Capital", "Closed investment sales by Exodus Capital across New York, New Jersey, Connecticut and beyond.", body, "/properties/track-record/", header_light=True)


def page_property(p):
    slides = "".join('<div class="property-hero__slide %s" data-slide><img src="%s" alt="%s" %s></div>' % (
        "is-active" if i == 0 else "", E(im["src"]), E(im["alt"] or p["title"]), 'loading="lazy"' if i else "") for i, im in enumerate(p["images"]))
    dots = ""
    if len(p["images"]) > 1:
        dots = '<div class="property-hero__dots">%s</div>' % "".join('<button data-dot aria-label="Photo %d"></button>' % (i + 1) for i in range(len(p["images"])))
    body = '<section class="property-hero" data-slides="5000">%s%s</section>' % (slides, dots)
    body += '''
<section class="property-info">
  <div class="container">
    <span class="property-info__label">%s</span>
    <h1>%s</h1>
    <div class="property-info__loc">%s</div>
    <div class="property-info__price">%s</div>
    <div class="property-info__arrow">%s</div>
  </div>
</section>''' % (E(p["status"]), E(p["title"]), E(p["location"]), E(p["price"]), icon("down2"))
    if p.get("schedule_tour"):
        img = p["images"][0]
        body += '''
<section class="tour">
  <div class="tour__img"><img src="%s" alt="%s" loading="lazy"></div>
  <div class="tour__form">
    <h2>Want to tour?</h2>
    %s
      <input type="hidden" name="property" value="%s">
      <div class="form__row"><input type="text" name="name" placeholder="Name" required aria-label="Name"><input type="email" name="email" placeholder="Email" required aria-label="Email"></div>
      <div class="form__row"><input type="tel" name="phone" placeholder="Phone" aria-label="Phone"><input type="date" name="date" aria-label="Preferred date" required></div>
      <select name="time" required aria-label="Preferred time"><option value="" disabled selected>Choose a time</option>%s</select>
      <div class="radio-row">
        <input type="radio" name="type" id="tour-person" value="In Person" checked><label for="tour-person">In Person</label>
        <input type="radio" name="type" id="tour-video" value="Via Video Chat"><label for="tour-video">Via Video Chat</label>
      </div>
      %s
      <div><button class="btn btn--light" type="submit">Schedule a Tour</button></div>
      <p class="form__status" aria-live="polite"></p>
    </form>
  </div>
</section>''' % (E(img["src"]), E(img["alt"] or p["title"]), form_open("tour-request", "form form--dark"), E(p["title"]),
                 "".join("<option>%s</option>" % t for t in ["09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM"]),
                 consent("tour-consent"))
    if p.get("lat") and p.get("lng"):
        body += '<section class="map"><iframe loading="lazy" title="Map of %s" src="https://maps.google.com/maps?q=%s,%s&z=15&output=embed"></iframe></section>' % (E(p["title"]), E(p["lat"]), E(p["lng"]))
    body += follow_strip() + cta_grid()
    og = p["images"][0]["src"] if p["images"] else None
    desc = p["meta_description"] or "%s — %s in %s. %s." % (p["title"], p["status"], p["location"], p["price"])
    return layout(p["meta_title"] or "%s | %s" % (p["title"], site["name"]), desc, body, "/properties/%s/" % p["slug"], header_light=False, og_image=og)


def page_testimonials():
    items = ""
    for i, t in enumerate(testimonials):
        long = len(t["quote"]) > 600
        items += '''
<div class="testimonial">
  <div><div class="testimonial__initial">%s</div></div>
  <div>
    <div class="testimonial__name">%s</div>
    %s
    <p class="testimonial__quote %s" id="quote-%d">%s</p>
    %s
  </div>
</div>''' % (E(t["name"][0]), E(t["name"]), ('<div class="testimonial__title">%s</div>' % E(t["title"])) if t.get("title") else "",
             "is-clamped" if long else "", i, E(t["quote"]),
             ('<button class="link-caps" data-readmore="quote-%d">Read More</button>' % i) if long else "")
    body = banner("Our Clientele", assets["cta_contact"])
    body += '<section class="section section--light" style="padding-top:24px"><div class="container container--narrow">%s</div></section>' % items
    body += follow_strip() + cta_grid()
    return layout("Testimonials | New York Investment Firm | Exodus Capital", "What clients say about working with Exodus Capital.", body, "/testimonials/")


def page_blog_index(page_no, total_pages):
    start = (page_no - 1) * POSTS_PER_PAGE
    chunk = posts[start:start + POSTS_PER_PAGE]
    cards = "".join(post_card(p) for p in chunk)
    pag = ""
    if total_pages > 1:
        def link(n, label=None, cur=False):
            href = "/blog/" if n == 1 else "/blog/page/%d/" % n
            return '<span class="is-current">%s</span>' % (label or n) if cur else '<a href="%s">%s</a>' % (href, label or n)
        parts = []
        if page_no > 1: parts.append(link(page_no - 1, "&lsaquo;"))
        parts += [link(n, cur=(n == page_no)) for n in range(1, total_pages + 1)]
        if page_no < total_pages: parts.append(link(page_no + 1, "&rsaquo;"))
        pag = '<nav class="pagination" aria-label="Pagination">%s</nav>' % "".join(parts)
    path = "/blog/" if page_no == 1 else "/blog/page/%d/" % page_no
    body = banner("Blog", assets["cta_updates"])
    body += '<section class="section section--light"><div class="container"><div class="blog-list">%s</div>%s</div></section>' % (cards, pag)
    body += cta_grid()
    title = "Blog | New York Investment Firm | Exodus Capital" + ("" if page_no == 1 else " | Page %d" % page_no)
    return layout(title, "Market insight and news from Exodus Capital.", body, path)


def page_blog_post(p):
    others = [o for o in posts if o["slug"] != p["slug"]][:3]
    url = site["url"] + "/blog/%s/" % p["slug"]
    share = '''
<div class="post-share">
  <a class="social-icon" target="_blank" rel="noopener" aria-label="Share on Facebook" href="https://www.facebook.com/sharer/sharer.php?u=%s">%s</a>
  <a class="social-icon" target="_blank" rel="noopener" aria-label="Share on X" href="https://twitter.com/intent/tweet?url=%s&text=%s">%s</a>
  <a class="social-icon" target="_blank" rel="noopener" aria-label="Share on LinkedIn" href="https://www.linkedin.com/shareArticle?mini=true&url=%s">%s</a>
  <a class="social-icon" aria-label="Share by email" href="mailto:?subject=%s&body=%s">%s</a>
</div>''' % (E(url), icon("facebook"), E(url), E(p["title"]), icon("x"), E(url), icon("linkedin"), E(p["title"]), E(url), icon("envelope"))
    hero = '''
<section class="banner banner--tall post-hero">
  <img class="banner__bg" src="%s" alt="%s" style="filter:none">
  <div class="container"><h1>%s</h1><p class="post-card__date" style="color:#fff">%s</p></div>
</section>''' % (E(p["image"] or assets["cta_updates"]), E(p["image_alt"]), E(p["title"]), E(nice_date(p["date"])))
    body = hero
    body += '<section class="section section--light"><div class="container"><article class="post-body">%s</article>%s</div></section>' % (p["body_html"], share)
    body += '<section class="section section--gray"><div class="container"><h2 class="related__title">Read More Articles</h2><div class="grid grid--3">%s</div></div></section>' % "".join(post_card(o) for o in others)
    body += cta_grid()
    return layout(p["meta_title"] or "%s | %s" % (p["title"], site["name"]), p["excerpt"] or p["title"], body, "/blog/%s/" % p["slug"], og_image=p["image"] or None)


def page_careers():
    c = site["careers"]
    hero_inner = '<span class="pretitle">%s</span><h1>%s</h1>' % (E(c["hero_pretitle"]), E(c["hero_title"]))
    body = hero_video("hero-home", hero_inner, overlay="hero__overlay hero__overlay--heavy")
    body += '<section class="section section--dark intro intro--light"><div class="container"><img class="intro__mark" src="%s" alt=""><h2>%s</h2><p class="intro__text">%s</p></div></section>' % (E(assets["x_mark"]), E(c["who_title"]), E(c["who_text"]))
    roles = "".join("<option>%s</option>" % E(r) for r in c["apply_roles"])
    body += '''
<section class="section section--light" id="apply">
  <div class="container">
    <div class="split">
      <div><h2>%s</h2><p style="margin-top:20px;color:var(--gray)">%s</p></div>
      <div>%s
        <input type="text" name="name" placeholder="Full Name *" required aria-label="Full name">
        <div class="form__row"><input type="email" name="email" placeholder="Email *" required aria-label="Email"><input type="tel" name="phone" placeholder="Phone" aria-label="Phone"></div>
        <select name="interest" required aria-label="What are you interested in?"><option value="" disabled selected>What are you interested in?</option>%s</select>
        %s
        <div><button class="btn btn--solid-dark" type="submit">Submit</button></div>
        <p class="form__status" aria-live="polite"></p>
      </form></div>
    </div>
  </div>
</section>''' % (E(c["apply_title"]), E(c["apply_text"]), form_open("careers"), roles, consent("careers-consent"))
    body += logo_row(assets["press"], title=c["press_title"], marquee=True)
    body += stats_block(c["stats"], title=c["stats_title"])
    fs = c["founder_social"]
    body += '''
<section class="section section--light">
  <div class="container">
    <div class="split">
      <div>
        <h2>%s</h2>
        <h3 style="margin:16px 0 24px">%s</h3>
        <div class="follow__links" style="justify-content:flex-start">%s</div>
      </div>
      <div class="video-poster" style="background-image:url(%s)">
        <button class="play-btn" data-video="https://www.youtube.com/embed/%s?autoplay=1" aria-label="Play video">%s</button>
      </div>
    </div>
  </div>
</section>''' % (E(c["founder_title"]), E(c["founder_name"]), social_links(fs), E(assets["founder_poster"]), E(c["founder_youtube_id"]), icon("play"))
    items = "".join("<li><div><strong>%s</strong>%s</div></li>" % (E(i["title"]), E(i["text"])) for i in c["apart_items"])
    body += '''
<section class="section section--dark">
  <div class="container">
    <div class="split split--reverse">
      <div><img src="%s" alt="Exodus Capital team" loading="lazy"></div>
      <div><h2 style="margin-bottom:28px">%s</h2><ul class="checklist">%s</ul><a class="btn btn--light" href="#apply">%s</a></div>
    </div>
  </div>
</section>''' % (E(assets["careers_team"]), E(c["apart_title"]), items, E(c["apart_button"]))
    if listings:
        body += property_carousel(c["featured_title"], listings, show_mark=False, view_all="/listings/", autoplay=0)
    cu = assets["careers_culture"]
    body += '''
<section class="culture">
  <div class="culture__tile"><h4>%s</h4><a class="btn btn--light" href="%s">%s</a></div>
  <div class="culture__img"><img src="%s" alt="" loading="lazy"></div>
  <div class="culture__img"><img src="%s" alt="" loading="lazy"></div>
</section>''' % (E(c["culture_title"]), E(c["culture_button"]["href"]), E(c["culture_button"]["label"]), E(cu[0]), E(cu[1]))
    quotes = "".join('<div class="review-slide %s" data-slide><p class="quote-slider__text">%s</p><div class="quote-slider__name">&mdash; %s</div></div>' % (
        "is-active" if i == 0 else "", E(t["quote"][:650].rsplit(" ", 1)[0] + ("..." if len(t["quote"]) > 650 else "")), E(t["name"])) for i, t in enumerate(testimonials))
    body += '''
<section class="section section--light">
  <div class="container">
    <h2 class="section__title">%s</h2>
    <div class="quote-slider" data-slides="8000">
      %s
      <div class="reviews__nav" style="color:var(--black)"><button class="arrow-btn" data-prev aria-label="Previous">%s</button><button class="arrow-btn" data-next aria-label="Next">%s</button></div>
      <p style="margin-top:36px"><a class="btn btn--dark" href="/testimonials/">View All Testimonials</a></p>
    </div>
  </div>
</section>''' % (E(c["testimonials_title"]), quotes, icon("left"), icon("right"))
    body += follow_strip("Follow Us on Instagram")
    body += cta_grid(left_title=c["cta_title"])
    return layout("Careers | New York Investment Firm | Exodus Capital", "Join Exodus Capital, a growing Tri-State investment sales brokerage.", body, "/careers/")


def slide_hero(video_key, slides, buttons):
    btns = "".join('<a class="btn %s" href="%s"%s>%s</a>' % ("btn--solid-light" if i == 0 else "btn--light", E(b["href"]), ' target="_blank" rel="noopener"' if b.get("external") else "", E(b["label"])) for i, b in enumerate(buttons))
    inner = '<div class="hero__slides" data-slides="6000">%s</div><div class="hero__buttons">%s</div>' % (
        "".join('<div class="hero__slide %s" data-slide><span class="pretitle">%s</span><h1>%s</h1></div>' % ("is-active" if i == 0 else "", E(s["pretitle"]), s["title"]) for i, s in enumerate(slides)), btns)
    return hero_video(video_key, inner)


def accordion(items):
    return '<div class="accordion">%s</div>' % "".join('<div class="accordion__item %s"><button class="accordion__btn" type="button"><h5>%s</h5></button><div class="accordion__body"><p>%s</p></div></div>' % (
        "is-open" if i == 0 else "", E(it["title"]), it["text"]) for i, it in enumerate(items))


def page_vision():
    v = site["vision"]
    body = slide_hero("hero-vision", v["slides"], v["slide_buttons"])
    body += '<section class="section section--dark"><div class="container"><h2 class="section__title">%s</h2>%s</div></section>' % (E(v["approach_title"]), accordion(v["approach"]))
    news = [dict(n, image=assets["news"][n["image"]]) for n in site["news"]]
    body += '<section class="section section--light"><div class="container"><h2 class="section__title">%s</h2>%s</div></section>' % (E(v["news_title"]), press_grid(news))
    body += reviews_section("Our Client Reviews")
    body += follow_strip() + cta_grid()
    return layout("Intuitive Approach | New York Real Estate | Exodus Capital", "The Exodus approach: equity evaluation, boots on the ground, market pollination and transitional real estate.", body, "/our-vision/")


def page_partnership():
    n = site["partnership"]
    body = slide_hero("hero-partnership", n["slides"], n["slide_buttons"])
    body += '<section class="section section--dark intro intro--light"><div class="container"><img src="%s" alt="Horvath &amp; Tremblay" style="width:200px;margin:0 auto 32px;filter:brightness(0) invert(1)"><p class="intro__text">%s</p></div></section>' % (E(assets["partner_logo"]), n["intro_text"])
    body += logo_row(assets["partner_press"], marquee=True)
    tiles = "".join('<a class="tile" href="%s" target="_blank" rel="noopener" style="background-image:url(%s)"><h3>%s</h3></a>' % (E(g["href"]), E(assets["partner_grid"][g["image"]]), E(g["title"])) for g in n["grid"])
    body += '<section class="section section--light" style="padding-top:0"><div class="container"><div class="tiles">%s</div></div></section>' % tiles
    body += '<section class="section section--gray"><div class="container">%s</div></section>' % accordion(n["accordion"])
    body += stats_block(n["stats"], title=n["stats_title"], cols=5)
    body += '<section class="section section--light text-center"><div class="container"><h2 style="margin-bottom:28px">%s</h2><a class="btn btn--dark" href="%s" target="_blank" rel="noopener">%s</a></div></section>' % (E(n["cta_text"]), E(n["cta_button"]["href"]), E(n["cta_button"]["label"]))
    body += follow_strip() + cta_grid()
    return layout("National Partnership | New York Investment Firm | Exodus Capital", "Exodus Capital's national 1031 exchange partnership with Horvath & Tremblay.", body, "/national-partnership/")


def page_privacy():
    body = '<section class="section section--light" style="padding-top:calc(var(--header-h) + 48px)"><div class="container container--narrow"><h1 style="font-size:28px;margin-bottom:32px">Privacy Policy</h1><div class="rich">%s</div></div></section>' % privacy_html
    return layout("Privacy Policy | Exodus Capital | New York Investment Firm", "Privacy policy and terms of use for exoduscapitalcre.com.", body, "/terms-and-conditions/", header_light=True)


def page_sitemap():
    def col(title, links):
        return '<div><h3>%s</h3><ul>%s</ul></div>' % (E(title), "".join('<li><a href="%s">%s</a></li>' % (E(h), E(t)) for t, h in links))
    pages = [("Home", "/"), ("Meet Our Team", "/team/"), ("Track Record", "/properties/track-record/"), ("Listings", "/listings/"), ("Testimonials", "/testimonials/"), ("Blog", "/blog/"), ("Careers", "/careers/"), ("Our Vision", "/our-vision/"), ("National Partnership", "/national-partnership/"), ("Privacy Policy", "/terms-and-conditions/")]
    body = '<section class="section section--light" style="padding-top:calc(var(--header-h) + 48px)"><div class="container"><h1 style="font-size:28px;margin-bottom:40px">Sitemap</h1><div class="sitemap-cols">%s%s%s%s%s</div></div></section>' % (
        col("Pages", pages), col("Team", [(a["name"], "/agent/%s/" % a["slug"]) for a in team]),
        col("Listings", [(p["title"], "/properties/%s/" % p["slug"]) for p in listings]),
        col("Track Record", [(p["title"], "/properties/%s/" % p["slug"]) for p in sold]),
        col("Blog", [(p["title"], "/blog/%s/" % p["slug"]) for p in posts]))
    return layout("Sitemap | Exodus Capital", "All pages on exoduscapitalcre.com.", body, "/sitemap/", header_light=True)


def page_404():
    body = '<section class="section section--light text-center" style="padding-top:calc(var(--header-h) + 96px);min-height:70vh"><div class="container"><h1 style="font-size:28px">Page not found</h1><p style="margin:20px 0 32px;color:var(--gray)">The page you are looking for does not exist or has moved.</p><a class="btn btn--dark" href="/">Back to Home</a></div></section>'
    return layout("Page not found | Exodus Capital", "Page not found.", body, "/404.html", header_light=True)


# ---------------------------------------------------------------- build
def build():
    # build into a fresh folder, then swap it in, so a running preview never sees a half-built site
    global DIST
    final, DIST = DIST, DIST.with_name(DIST.name + ".new")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copytree(STATIC / "assets", DIST / "assets")
    shutil.copytree(STATIC / "media", DIST / "media", ignore=shutil.ignore_patterns(".*"))
    shutil.copy(DIST / assets["x_mark"].lstrip("/"), DIST / "favicon.png")

    urls = []

    def emit(url, content):
        write(page_path(url), postprocess(content))
        urls.append(url)

    emit("/", page_home())
    emit("/team/", page_team())
    for a in team:
        emit("/agent/%s/" % a["slug"], page_agent(a))
    emit("/listings/", page_listings())
    emit("/properties/track-record/", page_track_record())
    for p in properties:
        emit("/properties/%s/" % p["slug"], page_property(p))
    emit("/testimonials/", page_testimonials())
    total_pages = max(1, -(-len(posts) // POSTS_PER_PAGE))
    for n in range(1, total_pages + 1):
        emit("/blog/" if n == 1 else "/blog/page/%d/" % n, page_blog_index(n, total_pages))
    for p in posts:
        emit("/blog/%s/" % p["slug"], page_blog_post(p))
    emit("/careers/", page_careers())
    emit("/our-vision/", page_vision())
    emit("/national-partnership/", page_partnership())
    emit("/terms-and-conditions/", page_privacy())
    emit("/sitemap/", page_sitemap())
    write("404.html", postprocess(page_404()))
    write(".nojekyll", "")   # GitHub Pages: serve files starting with "_" as-is

    if FLAT:
        if final.exists():
            shutil.rmtree(final)
        DIST.rename(final)
        DIST = final
        print("built %d flat pages into %s" % (len(urls) + 1, DIST))
        return

    today = datetime.date.today().isoformat()
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s</urlset>\n' % "".join(
        "  <url><loc>%s</loc><lastmod>%s</lastmod></url>\n" % (E(site["url"] + u), today) for u in urls))
    write("robots.txt", "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % site["url"])
    # Netlify / Cloudflare Pages: long cache for fingerprint-free media, pretty 404
    write("_headers", "/media/*\n  Cache-Control: public, max-age=2592000\n/assets/*\n  Cache-Control: public, max-age=86400\n")
    write("_redirects", "/profile /team/ 301\n/copy-team /team/ 301\n/team1 /team/ 301\n/team-back-up /team/ 301\n")
    if final.exists():
        shutil.rmtree(final)
    DIST.rename(final)
    DIST = final
    print("built %d pages into %s" % (len(urls) + 1, DIST))


if __name__ == "__main__":
    build()
