"""
アイコン画像を作る（任意）:  python make_icons.py
config.py の TEAM_COLOR を背景にしたサッカーボールのアイコンを static/icons/ に書き出す。
チームカラーを変えたときに実行し直す。Pillow が必要（pip install pillow）。
作られるもの: favicon.svg, apple-touch-icon.png(180), icon-192.png, icon-512.png
"""
import math
import os

import config

OUT = os.path.join(config.BASE_DIR, "static", "icons")
os.makedirs(OUT, exist_ok=True)


def pentagon(cx, cy, r, rotate=-90):
    """中心 (cx, cy)・半径 r の正五角形の頂点"""
    return [(cx + r * math.cos(math.radians(rotate + 72 * i)),
             cy + r * math.sin(math.radians(rotate + 72 * i))) for i in range(5)]


# ---- SVG（favicon 用。ブラウザのタブに出る） ----
pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in pentagon(50, 50, 16))
outer = [pentagon(50 + 29 * math.cos(math.radians(-90 + 72 * i)),
                  50 + 29 * math.sin(math.radians(-90 + 72 * i)), 8.5, rotate=-90 + 72 * i + 36)
         for i in range(5)]
outer_svg = "".join('<polygon points="%s" fill="#111"/>' % " ".join(f"{x:.1f},{y:.1f}" for x, y in p) for p in outer)
svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<rect width="100" height="100" rx="22" fill="{config.TEAM_COLOR}"/>
<circle cx="50" cy="50" r="38" fill="#fff"/>
<polygon points="{pts}" fill="#111"/>
{outer_svg}
</svg>
"""
with open(os.path.join(OUT, "favicon.svg"), "w", encoding="utf-8") as f:
    f.write(svg)

# ---- PNG（ホーム画面用） ----
try:
    from PIL import Image, ImageDraw
except ImportError:
    print("favicon.svg だけ作りました。PNG も作るには  pip install pillow  してから実行してください。")
    raise SystemExit

for name, size in (("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512)):
    S = 8                                        # 大きく描いて縮小するとフチがなめらかになる
    big = size * S
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = big / 100                                # SVG と同じ座標系（0〜100）で描く
    d.rounded_rectangle([0, 0, big, big], radius=22 * k, fill=config.TEAM_COLOR)
    d.ellipse([12 * k, 12 * k, 88 * k, 88 * k], fill="#fff")
    d.polygon([(x * k, y * k) for x, y in pentagon(50, 50, 16)], fill="#111")
    for p in outer:
        d.polygon([(x * k, y * k) for x, y in p], fill="#111")
    img = img.resize((size, size), Image.LANCZOS)
    img.save(os.path.join(OUT, name))

print(f"OK: {OUT} にアイコンを作りました（色: {config.TEAM_COLOR}）")
