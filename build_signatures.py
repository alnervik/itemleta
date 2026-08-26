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

WIKI_API = "https://tibia.fandom.com/api.php"
WIKI_FILEPATH = "https://tibia.fandom.com/wiki/Special:FilePath/{}"
WIKI_CATEGORY = "Category:Objects with Object IDs"

OUT_FILE = Path("data/signatures.json")
GRID_SIZE = 4          # signatur-upplösning för matchning
THUMB_SIZE = 32         # visningsstorlek i UI

HEADERS = {"User-Agent": "tibia-item-matcher/1.0 (personal fan project)"}


def get_item_names() -> list[str]:
    """Hämtar alla sidtitlar i kategorin 'Objects with Object IDs' via MediaWiki-API:t.

    TibiaData API har INGET items-endpoint (bara karaktärer/världar/highscores/etc),
    så itemlistan måste hämtas direkt från TibiaWiki istället.
    """
    names = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": WIKI_CATEGORY,
        "cmlimit": "500",
        "format": "json",
    }
    while True:
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for member in data.get("query", {}).get("categorymembers", []):
            title = member["title"]
            # Hoppa över eventuella undersidor/kategorisidor som inte är faktiska items
            if ":" not in title:
                names.append(title)

        cont = data.get("continue", {}).get("cmcontinue")
        if not cont:
            break
        params["cmcontinue"] = cont
        time.sleep(0.2)

    return sorted(set(names))


def download_sprite(name: str) -> Image.Image | None:
    safe_name = name.replace(" ", "_")
    url = WIKI_FILEPATH.format(f"{safe_name}.gif")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
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
