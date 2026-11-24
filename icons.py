#!/usr/bin/env python3
"""Generate the home-screen icons and the web app manifest.

Run once, or again after changing the palette:  python3 icons.py

Three ascending bars in the bumper-plate colours the dashboard already uses
for its crowding ramp, on the same iron background. A dark tile reads well
against most phone wallpapers, and iOS rounds the corners itself, so these
are full-bleed squares with no transparency.
"""
import json
import os

from PIL import Image, ImageDraw

IRON = (0x1F, 0x1D, 0x1B)
BARS = [(0x2F, 0x7D, 0x3A), (0xE8, 0xB5, 0x17), (0xC8, 0x32, 0x2B)]
HEIGHTS = [0.42, 0.68, 0.94]          # of the content box, ascending

os.makedirs("assets", exist_ok=True)


def draw(size):
    img = Image.new("RGB", (size, size), IRON)
    d = ImageDraw.Draw(img)
    pad = size * 0.20                  # generous: iOS crops a little
    box = size - 2 * pad
    gap = box * 0.13
    w = (box - 2 * gap) / 3
    base = pad + box
    for i, (col, h) in enumerate(zip(BARS, HEIGHTS)):
        x0 = pad + i * (w + gap)
        y0 = base - box * h
        d.rectangle([x0, y0, x0 + w, base], fill=col)
    return img


for size, name in [(192, "icon-192.png"), (512, "icon-512.png"),
                   (180, "apple-touch-icon.png"), (32, "favicon-32.png")]:
    p = os.path.join("assets", name)
    draw(size).save(p, "PNG", optimize=True)
    print("wrote %-24s %d x %d" % (p, size, size))

manifest = {
    "name": "UF Rec Crowd",
    "short_name": "Rec Crowd",
    "description": "How busy UF RecSports is right now.",
    "start_url": "./",
    "scope": "./",
    "display": "standalone",
    "background_color": "#E8E6E0",
    "theme_color": "#1F1D1B",
    "orientation": "portrait-primary",
    "icons": [
        {"src": "assets/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "assets/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "assets/icon-512.png", "sizes": "512x512", "type": "image/png",
         "purpose": "maskable"},
    ],
}
with open("manifest.webmanifest", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
print("wrote manifest.webmanifest")
