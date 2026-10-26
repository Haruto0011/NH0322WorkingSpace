"""
Generate app icons in the team color.

    python make_icons.py

Writes static/icons/favicon.svg, apple-touch-icon.png (180px),
icon-192.png and icon-512.png. PNG output requires Pillow.
"""
import math
import os

import config

OUT = os.path.join(config.BASE_DIR, "static", "icons")
os.makedirs(OUT, exist_ok=True)


def pentagon(cx, cy, r, rotate=-90):
    return [(cx + r * math.cos(math.radians(rotate + 72 * i)),
             cy + r * math.sin(math.radians(rotate + 72 * i))) for i in range(5)]


# Ball geometry in a 0-100 coordinate space: one central pentagon and five around it.
center = pentagon(50, 50, 16)
outer = [pentagon(50 + 29 * math.cos(math.radians(-90 + 72 * i)),
                  50 + 29 * math.sin(math.radians(-90 + 72 * i)), 8.5, rotate=-90 + 72 * i + 36)
         for i in range(5)]


def points(poly):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in poly)


svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<rect width="100" height="100" rx="22" fill="{config.TEAM_COLOR}"/>
<circle cx="50" cy="50" r="38" fill="#fff"/>
<polygon points="{points(center)}" fill="#111"/>
{"".join(f'<polygon points="{points(p)}" fill="#111"/>' for p in outer)}
</svg>
"""
with open(os.path.join(OUT, "favicon.svg"), "w", encoding="utf-8") as f:
    f.write(svg)

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("favicon.svg written. Install Pillow (pip install pillow) to also generate PNG icons.")
    raise SystemExit

for name, size in (("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512)):
    scale = 8  # render large, then downsample for smooth edges
    big = size * scale
    k = big / 100
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, big, big], radius=22 * k, fill=config.TEAM_COLOR)
    d.ellipse([12 * k, 12 * k, 88 * k, 88 * k], fill="#fff")
    d.polygon([(x * k, y * k) for x, y in center], fill="#111")
    for p in outer:
        d.polygon([(x * k, y * k) for x, y in p], fill="#111")
    img.resize((size, size), Image.LANCZOS).save(os.path.join(OUT, name))

print(f"icons written to {OUT} (color {config.TEAM_COLOR})")
