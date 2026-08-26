"""
Bygger data/signatures.json — en komprimerad databas med nedskalade
färgsignaturer + små thumbnails för alla Tibia-items.

Körs av GitHub Actions (se .github/workflows/build-data.yml), där nätverket
kan nå tibiadata.com och tibia.fandom.com. Kör INTE detta i en sandlåda med
begränsad nätverksåtkomst.

    pip install requests pillow
    python build_signatures.py
"""

import base64
import io
import json
import time
from pathlib import Path

import requests
from PIL import Image

ITEM_LIST_URL = "https://api.tibiadata.com/v4/items"
WIKI_FILEPATH = "https://tibia.fandom.com/wiki/Special:FilePath/{}"

OUT_FILE = Path("data/signatures.json")
GRID_SIZE = 4          # signatur-upplösning för matchning
THUMB_SIZE = 32         # visningsstorlek i UI


def get_item_names() -> list[str]:
    resp = requests.get(ITEM_LIST_URL, timeout=30)
    resp.raise_for_status()
    items = resp.json()["items"]["item_list"]
    return sorted({item["name"] for item in items if item.get("name")})


def download_sprite(name: str) -> Image.Image | None:
    safe_name = name.replace(" ", "_")
    url = WIKI_FILEPATH.format(f"{safe_name}.gif")
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200 or not resp.content:
            return None
        return Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except Exception:
        return None


def to_signature(img: Image.Image, grid: int = GRID_SIZE) -> list[int]:
    small = img.resize((grid, grid), Image.BOX)
    flat = []
    for r, g, b, a in small.getdata():
        flat.extend([r, g, b, a])
    return flat


def to_thumb_b64(img: Image.Image, size: int = THUMB_SIZE) -> str:
    thumb = img.resize((size, size), Image.NEAREST)
    buf = io.BytesIO()
    thumb.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def main():
    print("Hämtar itemlista...")
    names = get_item_names()
    print(f"  {len(names)} items")

    entries = []
    for i, name in enumerate(names):
        img = download_sprite(name)
        if img is None:
            continue
        entries.append({
            "name": name,
            "sig": to_signature(img),
            "thumb": to_thumb_b64(img),
        })
        if i % 100 == 0:
            print(f"  {i}/{len(names)}")
        time.sleep(0.15)  # var snäll mot wikin

    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(
        json.dumps({"grid": GRID_SIZE, "items": entries}, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Klart. {len(entries)} items skrivna till {OUT_FILE}")


if __name__ == "__main__":
    main()
