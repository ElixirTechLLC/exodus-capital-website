#!/usr/bin/env python3
"""
Shrink images in static/media for the web (macOS `sips`, no extra installs).

- Anything wider/taller than MAX_PX is scaled down to MAX_PX on its longest side.
- Opaque PNG photographs are re-encoded as JPEG (quality 82) and every
  reference in data/*.json is updated from .png to .jpg.
- PNGs with transparency (logos) stay PNG.
- Already-small files are left alone. Safe to re-run.

Usage:  python3 tools/optimize_media.py [website-dir]
"""
import pathlib, re, subprocess, sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
MEDIA = ROOT / "static" / "media"
DATA = ROOT / "data"
MAX_PX = 1600
JPEG_Q = 78


def sips_get(path, key):
    out = subprocess.run(["sips", "-g", key, str(path)], capture_output=True, text=True).stdout
    return out.strip().split(":")[-1].strip()


import json
PHOTOS = set()
for name in ("properties.json", "blog.json", "team.json"):
    PHOTOS.update(re.findall(r'"/media/([^"]+)"', (DATA / name).read_text()))

MANIFEST = MEDIA / ".optimized.json"       # names already processed; re-encoding twice only loses quality
done = set(json.loads(MANIFEST.read_text())) if MANIFEST.exists() else set()

renamed = {}
for f in sorted(MEDIA.iterdir()):
    if f.suffix.lower() not in (".jpg", ".jpeg", ".png") or f.name in done:
        continue
    done.add(f.name)
    w, h = int(sips_get(f, "pixelWidth")), int(sips_get(f, "pixelHeight"))
    alpha = sips_get(f, "hasAlpha") == "yes"
    size_before = f.stat().st_size
    target = f
    args = []
    if max(w, h) > MAX_PX:
        args += ["-Z", str(MAX_PX)]
    photo = f.name in PHOTOS  # property/blog/team photos: JPEG even if the PNG carries an (unused) alpha channel
    if f.suffix.lower() == ".png" and (not alpha or photo) and size_before > 200_000:
        target = f.with_suffix(".jpg")
        args += ["-s", "format", "jpeg", "-s", "formatOptions", str(JPEG_Q)]
    elif f.suffix.lower() in (".jpg", ".jpeg") and size_before > 400_000:
        args += ["-s", "formatOptions", str(JPEG_Q)]
    if not args:
        continue
    tmp = target.with_name(target.stem + ".opt" + target.suffix)
    subprocess.run(["sips", *args, str(f), "--out", str(tmp)], capture_output=True, check=True)
    if tmp.stat().st_size >= size_before and max(w, h) <= MAX_PX:
        tmp.unlink()          # re-encoding did not help; keep the original
        continue
    if target != f:
        f.unlink()
        renamed[f.name] = target.name
        done.add(target.name)
    tmp.replace(target)
    print("%-45s %dx%d %6dK -> %6dK %s" % (f.name, w, h, size_before // 1024, target.stat().st_size // 1024, target.name if target != f else ""))

if renamed:
    for j in DATA.glob("*.json"):
        s = j.read_text()
        for old, new in renamed.items():
            s = s.replace("/media/" + old, "/media/" + new)
        j.write_text(s)
    print("updated %d references in data/*.json" % len(renamed))
MANIFEST.write_text(json.dumps(sorted(done)))
total = sum(p.stat().st_size for p in MEDIA.iterdir() if not p.name.startswith("."))
print("media folder now %.1f MB" % (total / 1e6))
