# Exodus Capital website

A self-hosted rebuild of exoduscapitalcre.com. It is a **static site**: plain
HTML, CSS and JavaScript generated from a few JSON files, so it can be hosted
for free (Netlify, Cloudflare Pages, GitHub Pages) with no server, no database
and no monthly platform fee.

```
website/
├── build.py                 the page templates; run it to generate dist/
├── data/
│   ├── site.json            contact info, nav, stats, copy for every page
│   ├── properties.json      every listing / closed deal (one object each)
│   ├── team.json            agents: bio, photo, press mentions
│   ├── blog.json            blog posts (title, date, hero image, body HTML)
│   ├── testimonials.json    client reviews
│   ├── assets.json          which image file is the logo, press logos, etc.
│   └── privacy.html         the privacy policy text
├── static/
│   ├── assets/site.css      the stylesheet
│   ├── assets/site.js       menu, modals, carousels, forms
│   └── media/               all images and videos (already web-sized)
├── tools/
│   ├── extract_from_luxurypresence.py   one-time import from the old site
│   └── optimize_media.py                shrinks new images for the web
└── dist/                    the generated site (upload this folder)
```

## Build

Requires only Python 3.9+ (already on every Mac).

```bash
cd website && python3 build.py
```

Preview locally:

```bash
cd website && python3 -m http.server 8787 --directory dist
```

then open http://localhost:8787.

## Everyday edits

**Add or change a listing** – edit `data/properties.json`. Each entry:

```json
{
  "slug": "191-bond-street",            -> page lives at /properties/191-bond-street/
  "status": "For Sale",                 -> "For Sale", "Under Contract" or "Sold"
  "title": "191 Bond Street",
  "location": "Boerum Hill, New York",
  "price": "$2,700,000",
  "images": [{"src": "/media/191-bond.jpg", "alt": "Corner building"}],
  "lat": "40.68", "lng": "-73.98",      -> map on the page (optional)
  "schedule_tour": true,                -> shows the "Want to tour?" form
  "section": "listings",                -> "listings" (active) or "track-record" (sold)
  "order": 0,                           -> position within its list (lower = earlier)
  "hidden": false                       -> true keeps the page but drops it from every list
}
```

Drop the photo into `static/media/`, run `python3 tools/optimize_media.py`
once so it is resized for the web, then `python3 build.py`.

**Mark a deal as sold** – change `status` to `"Sold"` and `section` to
`"track-record"`. Track-record order is by `order`; the import set it to the
negative sale price so bigger deals come first.

**Add a blog post** – add an object to `data/blog.json`: `slug`, `title`,
`date` (`YYYY-MM-DD`), `image`, `excerpt` and `body_html` (paragraphs, headings,
lists and links as HTML). Newest date appears first.

**Team** – `data/team.json`. `listed: true` puts the person on the Team page
grid; everyone gets a profile page at `/agent/<slug>/`.

**Stats, phone numbers, address, page copy** – `data/site.json`.

**Look and feel** – `static/assets/site.css`. Colours and fonts are the
variables at the top of the file.

## Contact forms

The forms (Contact Us, Register for market updates, Careers, Schedule a Tour)
post wherever `forms` in `data/site.json` says:

- `"provider": "netlify"` (default) – works automatically when the site is on
  Netlify. Submissions appear under *Forms* in the Netlify dashboard and can be
  emailed to you. Free tier: 100 submissions/month.
- `"provider": "custom", "action": "https://..."` – post to any endpoint that
  accepts a normal form POST: Formspree, Web3Forms, a Cloudflare Worker, or a
  **Salesforce Web-to-Lead** URL so leads land directly in the Exodus org.

## Hosting (free)

1. Push the `website/` folder to a GitHub repository.
2. On Netlify (or Cloudflare Pages): *New site from Git*, build command
   `python3 build.py`, publish directory `dist`.
3. Add the custom domain `exoduscapitalcre.com` in the host's dashboard and
   point the DNS records it gives you at it (the host issues the SSL
   certificate automatically).
4. Keep the Luxury Presence site live until the new one is verified, then
   cancel.

No build step on the host is needed either: `dist/` can be uploaded as-is
(drag-and-drop on Netlify).

## URL compatibility

All public URLs from the old site are preserved (`/team`, `/listings`,
`/properties/<slug>`, `/agent/<slug>`, `/blog/<slug>`,
`/properties/track-record`, `/terms-and-conditions`, `/careers`,
`/testimonials`, `/our-vision`, `/national-partnership`, `/sitemap`), and
`sitemap.xml` / `robots.txt` are generated. `_redirects` maps the old
leftover pages (`/profile`, `/copy-team`, `/team1`, `/team-back-up`) to
`/team/`.

## What is different from the Luxury Presence version

- The Instagram feed widget is replaced by a "Follow us" strip (the feed needed
  Luxury Presence's Instagram API connection).
- The map on property pages is a plain Google Maps embed (no API key needed),
  shown in black and white.
- The cookie banner, Luxury Presence tracking scripts and the
  "Powered by Luxury Presence" footer line are gone. Add your own analytics
  snippet to `analytics_html` in `data/site.json` if you want one.
