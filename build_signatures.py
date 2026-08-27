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
# Bara dessa kategorier tas med — matchningen begränsas medvetet till
# utrustning, vapen och mat istället för alla items i spelet.
WIKI_CATEGORIES = ["Category:Body Equipment", "Category:Weapons", "Category:Food"]

OUT_FILE = Path("data/signatures.json")
GRID_SIZE = 4          # signatur-upplösning för matchning
THUMB_SIZE = 32         # visningsstorlek i UI

HEADERS = {"User-Agent": "tibia-item-matcher/1.0 (personal fan project)"}


def _collect_category(cmtitle: str, seen_categories: set[str], names: set[str]) -> None:
    """Hämtar sidtitlar i en kategori och går rekursivt in i eventuella underkategorier.

    'Category:Body Equipment' t.ex. innehåller inga items direkt, bara
    underkategorier som Armors/Helmets/Boots/Shields/Amulets/Rings/Legs/
    Spellbooks — så vi måste följa kategoriträdet nedåt istället för att
    bara läsa av toppnivån.
    """
    if cmtitle in seen_categories:
        return
    seen_categories.add(cmtitle)

    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": cmtitle,
        "cmlimit": "500",
        "format": "json",
    }
    while True:
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for member in data.get("query", {}).get("categorymembers", []):
            title = member["title"]
            if member.get("ns") == 14:  # Category-namnrymden -> gräv djupare
                _collect_category(title, seen_categories, names)
            elif ":" not in title:
                names.add(title)

        cont = data.get("continue", {}).get("cmcontinue")
        if not cont:
            break
        params["cmcontinue"] = cont
        time.sleep(0.2)


def get_item_names() -> list[str]:
    """Hämtar alla sidtitlar under WIKI_CATEGORIES (inkl. underkategorier) via MediaWiki-API:t.

    TibiaData API har INGET items-endpoint (bara karaktärer/världar/highscores/etc),
    så itemlistan måste hämtas direkt från TibiaWiki istället.
    """
    seen_categories: set[str] = set()
    names: set[str] = set()
    for category in WIKI_CATEGORIES:
        _collect_category(category, seen_categories, names)
    return sorted(names)


def get_image_urls(names: list[str], batch_size: int = 50) -> dict[str, str]:
    """Slår upp de riktiga CDN-adresserna för varje items bildfil via MediaWiki-API:t.

    Vi undviker medvetet att hämta bilder direkt från Special:FilePath (som är en
    omdirigeringssida på själva wiki-domänen) eftersom Fandoms Cloudflare-skydd
    ofta blockerar den vägen för icke-webbläsarklienter. imageinfo-anropet ger oss
    istället den slutgiltiga static.wikia.nocookie.net-adressen, som är statiska
    filer utan samma bot-skydd.
    """
    urls: dict[str, str] = {}
    for i in range(0, len(names), batch_size):
        batch = names[i:i + batch_size]
        titles = "|".join(f"File:{n.replace(' ', '_')}.gif" for n in batch)
        params = {
            "action": "query",
            "titles": titles,
            "prop": "imageinfo",
            "iiprop": "url",
            "format": "json",
        }
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            title = page.get("title", "")
            info = page.get("imageinfo")
            if not (title.startswith("File:") and title.endswith(".gif") and info):
                continue
            name = title[len("File:"):-len(".gif")].replace("_", " ")
            urls[name] = info[0]["url"]
        print(f"  slog upp {min(i + batch_size, len(names))}/{len(names)} bild-URL:er", flush=True)
        time.sleep(0.3)
    return urls


def download_sprite(name: str, image_url: str | None) -> Image.Image | None:
    if image_url is None:
        print(f"    ingen bild hittades för: {name}", flush=True)
        return None
    try:
        resp = requests.get(image_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200 or not resp.content:
            print(f"    miss ({resp.status_code}): {name}", flush=True)
            return None
        return Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except Exception as e:
        print(f"    fel ({e}): {name}", flush=True)
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
    print("Hämtar itemlista...", flush=True)
    names = get_item_names()
    print(f"  {len(names)} items", flush=True)

    print("Slår upp bild-URL:er...", flush=True)
    image_urls = get_image_urls(names)
    print(f"  {len(image_urls)}/{len(names)} bild-URL:er hittade", flush=True)

    entries = []
    for i, name in enumerate(names):
        img = download_sprite(name, image_urls.get(name))
        if img is None:
            continue
        entries.append({
            "name": name,
            "sig": to_signature(img),
            "thumb": to_thumb_b64(img),
        })
        if i % 25 == 0:
            print(f"  {i}/{len(names)}  (hittills lyckade: {len(entries)})", flush=True)
        time.sleep(0.1)

    print(f"\nTotalt: {len(entries)}/{len(names)} sprites hämtade.", flush=True)

    # Säkerhetsspärr: om nästan allt misslyckades (t.ex. Fandom blockerar CI-IP:n)
    # ska vi INTE skriva över en fungerande databas med skräpdata.
    MIN_EXPECTED = 300
    if len(entries) < MIN_EXPECTED:
        print(
            f"FEL: bara {len(entries)} items hämtades (minst {MIN_EXPECTED} förväntades). "
            "Avbryter utan att skriva/committa — troligen blockerad av Fandom. "
            "Se statuskoderna ovan (403 = blockerad, 404 = fel filnamn/format)."
        )
        raise SystemExit(1)

    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(
        json.dumps({"grid": GRID_SIZE, "items": entries}, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Klart. {len(entries)} items skrivna till {OUT_FILE}")


if __name__ == "__main__":
    main()