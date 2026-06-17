#!/usr/bin/env python3
"""Generate the Rebrickable-style parts checklist from CSV inputs.

Drop one or more CSV files into the csv/ folder. Each file must have:

    Part,Color,Quantity

This script combines matching Part+Color rows, enriches them with
Rebrickable public data, and regenerates the checklist app data.
"""

from __future__ import annotations

import argparse
import colorsys
import csv
import gzip
import json
import re
import sys
import urllib.request
from collections import OrderedDict
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CSV_DIR = ROOT / "csv"
CACHE_DIR = ROOT / ".rebrickable-cache"

DATA_JSON = ROOT / "rebrickable-checklist-data.json"
DATA_JS = ROOT / "rebrickable-checklist-data.js"
HTML_FILE = ROOT / "rebrickable-checklist.html"

DOWNLOADS = {
    "colors.csv.gz": "https://cdn.rebrickable.com/media/downloads/colors.csv.gz",
    "parts.csv.gz": "https://cdn.rebrickable.com/media/downloads/parts.csv.gz",
    "elements.csv.gz": "https://cdn.rebrickable.com/media/downloads/elements.csv.gz",
    "part_categories.csv.gz": "https://cdn.rebrickable.com/media/downloads/part_categories.csv.gz",
    "part_relationships.csv.gz": "https://cdn.rebrickable.com/media/downloads/part_relationships.csv.gz",
}

APP_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rebrickable Parts Checklist</title>
  <link rel="stylesheet" href="rebrickable-checklist.css">
</head>
<body>
  <header class="topbar">
    <div>
      <h1>Parts Checklist</h1>
      <p id="sourceLabel">Loading parts...</p>
    </div>
    <div class="summary" aria-live="polite">
      <span><strong id="completeCount">0</strong>/<span id="totalCount">0</span> complete</span>
      <span><strong id="ownedCount">0</strong>/<span id="neededCount">0</span> pieces</span>
    </div>
  </header>

  <main>
    <section class="controls" aria-label="Checklist controls">
      <label class="search">
        <span>Search</span>
        <input id="searchInput" type="search" placeholder="Part, color, or name">
      </label>
      <div class="segmented" role="group" aria-label="Filter parts">
        <button class="active" type="button" data-filter="all">All</button>
        <button type="button" data-filter="missing">Missing</button>
        <button type="button" data-filter="partial">Partial</button>
        <button type="button" data-filter="complete">Complete</button>
      </div>
      <button id="exportButton" class="utility" type="button">Export</button>
      <button id="resetButton" class="utility danger" type="button">Reset</button>
    </section>

    <section id="partsGrid" class="parts-grid" aria-live="polite"></section>
  </main>

  <template id="partTemplate">
    <article class="part-card">
      <div class="image-wrap">
        <img alt="">
      </div>
      <div class="qty-line"></div>
      <div class="part-name"></div>
      <div class="counter" aria-label="Owned count">
        <button class="minus" type="button" aria-label="Decrease owned count">-</button>
        <input type="number" min="0" inputmode="numeric" aria-label="Owned quantity">
        <button class="plus" type="button" aria-label="Increase owned count">+</button>
      </div>
      <label class="check-wrap">
        <input type="checkbox" aria-label="Mark complete">
        <span></span>
      </label>
    </article>
  </template>

  <script src="rebrickable-checklist-data.js"></script>
  <script src="rebrickable-checklist.js"></script>
</body>
</html>
"""

CATEGORY_ORDER_NAMES = [
    "Bricks",
    "Bricks Curved",
    "Bricks Round and Cones",
    "Bricks Sloped",
    "Plates",
    "Plates Angled",
    "Plates Round and Dishes",
    "Plates Special",
    "Tiles",
    "Tiles Round and Curved",
    "Tiles Special",
    "Wedges",
    "Hinges, Arms and Turntables",
    "Technic Bricks",
    "Technic Beams",
    "Technic Connectors",
    "Technic Pins",
    "Technic Axles",
    "Technic Gears",
    "Technic Special",
    "Bars, Ladders and Fences",
    "Panels",
    "Windscreens and Fuselage",
    "Windows and Doors",
    "Transportation - Land",
    "Transportation - Sea and Air",
    "Wheels and Tyres",
    "Minifig Accessories",
    "Minifig Heads",
    "Minifig Upper Body",
    "Minifig Lower Body",
    "Minifig Headwear",
    "Minifigs",
    "Plants and Animals",
    "Energy Effects",
    "HO Scale",
    "Large Buildable Figures",
    "Other",
    "Non-LEGO",
]

# Known Rebrickable image aliases for parts where the exact element/color URL 404s.
KNOWN_IMAGE_ALIASES = {
    "3069bpr0030-72": "https://cdn.rebrickable.com/media/parts/ldraw/72/3069b.png",
    "3023-33": "https://cdn.rebrickable.com/media/parts/ldraw/33/3023b.png",
    "32556-19": "https://cdn.rebrickable.com/media/parts/ldraw/19/32556a.png",
    "4079b-70": "https://cdn.rebrickable.com/media/parts/ldraw/70/4079.png",
    "4079b-19": "https://cdn.rebrickable.com/media/parts/ldraw/19/4079.png",
    "3023-25": "https://cdn.rebrickable.com/media/parts/ldraw/25/3023b.png",
    "3023-15": "https://cdn.rebrickable.com/media/parts/ldraw/15/3023b.png",
    "98138pr0010-179": "https://cdn.rebrickable.com/media/parts/ldraw/179/98138.png",
    "61409-72": "https://cdn.rebrickable.com/media/parts/ldraw/72/61409b.png",
    "57909a-72": "https://cdn.rebrickable.com/media/parts/ldraw/72/57909.png",
    "60481-15": "https://cdn.rebrickable.com/media/parts/ldraw/15/60481a.png",
    "4497-1103": "https://cdn.rebrickable.com/media/parts/ldraw/179/4497.png",
}

FRACTION_RE = r"\d+(?:/\d+)?"
DIM_RE = re.compile(rf"({FRACTION_RE}(?:\s*x\s*{FRACTION_RE})+)")
NUMBER_RE = re.compile(r"(\d+(?:/\d+)?)")
PRINT_RE = re.compile(r"\b(?:print|pattern|sticker(?:ed)?|decorated)\b", re.I)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the parts checklist from csv/*.csv.")
    parser.add_argument("--refresh-cache", action="store_true", help="Redownload Rebrickable metadata.")
    args = parser.parse_args()

    CSV_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)

    ensure_downloads(refresh=args.refresh_cache)
    payload = build_payload()
    write_outputs(payload)

    print(f"Generated {payload['totalRows']} unique part/color rows.")
    print(f"Read CSVs from: {CSV_DIR}")
    print(f"Updated: {DATA_JSON.name}, {DATA_JS.name}, {HTML_FILE.name}")
    return 0


def ensure_downloads(refresh: bool = False) -> None:
    for filename, url in DOWNLOADS.items():
        target = CACHE_DIR / filename
        if target.exists() and not refresh:
            continue
        print(f"Downloading {filename}...")
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            target.write_bytes(response.read())


def build_payload() -> dict:
    input_files = sorted(CSV_DIR.glob("*.csv"))
    if not input_files:
        raise SystemExit(f"No CSV files found in {CSV_DIR}")

    combined, source_rows = read_input_csvs(input_files)
    colors = read_csv_gz("colors.csv.gz")
    parts = read_csv_gz("parts.csv.gz")
    elements = read_csv_gz("elements.csv.gz")
    categories = read_csv_gz("part_categories.csv.gz")

    color_by_id = {str(row["id"]): row for row in colors}
    part_by_num = {row["part_num"]: row for row in parts}
    category_name = {int(row["id"]): row["name"] for row in categories}
    category_rank = {name: index for index, name in enumerate(CATEGORY_ORDER_NAMES)}
    element_by_key = pick_element_ids(elements, combined.values())

    rows = []
    for index, row in enumerate(combined.values()):
        item = build_part_item(index, row, color_by_id, part_by_num, category_name, element_by_key)
        rows.append(item)

    rows.sort(key=lambda item: sort_key(item, category_name, category_rank))
    for index, item in enumerate(rows):
        item["sourceIndex"] = index

    return {
        "generatedAt": "generated by generate_checklist.py",
        "source": ", ".join(source_rows.keys()),
        "sources": source_rows,
        "totalRows": len(rows),
        "sortOrder": "Hue/color blocks, then Rebrickable-like category/family/dimension order within each color.",
        "imageSource": "Rebrickable public download element IDs and cdn.rebrickable.com image URLs",
        "parts": rows,
    }


def read_input_csvs(input_files: list[Path]) -> tuple[OrderedDict[tuple[str, str], dict], dict[str, int]]:
    combined: OrderedDict[tuple[str, str], dict] = OrderedDict()
    source_rows = {}
    required = {"Part", "Color", "Quantity"}

    for path in input_files:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            source_rows[path.name] = 0
            continue
        missing = required - set(rows[0].keys())
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise SystemExit(f"{path.name} is missing required columns: {missing_text}")
        source_rows[path.name] = len(rows)

        for row in rows:
            key = (row["Part"].strip(), row["Color"].strip())
            if key not in combined:
                combined[key] = {"Part": key[0], "Color": key[1], "Quantity": 0, "sources": []}
            quantity = int(row["Quantity"])
            combined[key]["Quantity"] += quantity
            combined[key]["sources"].append({"file": path.name, "quantity": quantity})

    return combined, source_rows


def read_csv_gz(filename: str) -> list[dict[str, str]]:
    with gzip.open(CACHE_DIR / filename, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def pick_element_ids(elements: list[dict[str, str]], wanted_rows) -> dict[str, str]:
    wanted_keys = {f"{row['Part']}|{row['Color']}" for row in wanted_rows}
    element_by_key: dict[str, str] = {}
    for element in elements:
        key = f"{element['part_num']}|{element['color_id']}"
        if key in wanted_keys and key not in element_by_key and element.get("element_id"):
            element_by_key[key] = element["element_id"]
    return element_by_key


def build_part_item(
    index: int,
    row: dict,
    color_by_id: dict[str, dict[str, str]],
    part_by_num: dict[str, dict[str, str]],
    category_name: dict[int, str],
    element_by_key: dict[str, str],
) -> dict:
    color = color_by_id.get(str(row["Color"]), {})
    part = part_by_num.get(row["Part"], {})
    color_hex = "#" + color.get("rgb", "777777")
    hue, saturation, lightness = hex_to_hsl(color_hex)
    element_id = element_by_key.get(f"{row['Part']}|{row['Color']}", "")
    item_id = f"{row['Part']}-{row['Color']}"
    fallback_url = f"https://cdn.rebrickable.com/media/parts/ldraw/{row['Color']}/{row['Part']}.png"
    image_url = (
        f"https://cdn.rebrickable.com/media/parts/elements/{element_id}.jpg"
        if element_id
        else fallback_url
    )

    category_id = int(part["part_cat_id"]) if part.get("part_cat_id") else None
    item = {
        "id": item_id,
        "part": row["Part"],
        "colorId": int(row["Color"]),
        "colorName": color.get("name") or f"Color {row['Color']}",
        "colorHex": color_hex,
        "quantity": int(row["Quantity"]),
        "name": part.get("name") or f"Part {row['Part']}",
        "categoryId": category_id,
        "elementId": element_id,
        "imageUrl": image_url,
        "fallbackImageUrl": fallback_url,
        "hue": round(hue, 2),
        "saturation": round(saturation, 3),
        "lightness": round(lightness, 3),
        "sourceIndex": index,
        "sources": row["sources"],
    }
    if category_id in category_name:
        item["categoryName"] = category_name[category_id]
    if item_id in KNOWN_IMAGE_ALIASES:
        item["imageUrl"] = KNOWN_IMAGE_ALIASES[item_id]
        item["fallbackImageUrl"] = KNOWN_IMAGE_ALIASES[item_id]
        item["imageNote"] = "Uses a Rebrickable LDraw alias because the exact direct image URL is unavailable."
    return item


def hex_to_hsl(hex_value: str) -> tuple[float, float, float]:
    clean = (hex_value or "#777777").replace("#", "")
    try:
        red = int(clean[0:2], 16) / 255
        green = int(clean[2:4], 16) / 255
        blue = int(clean[4:6], 16) / 255
    except ValueError:
        red = green = blue = 0.47
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    return hue * 360, saturation, lightness


def sort_key(item: dict, category_name: dict[int, str], category_rank: dict[str, int]) -> tuple:
    return (
        color_block_key(item),
        category_key(item, category_name, category_rank),
        name_sort_key(item),
        natural_chunks(item.get("part", "")),
        item.get("id", ""),
    )


def color_block_key(item: dict) -> tuple:
    neutral = 1 if item.get("saturation", 0) < 0.08 else 0
    return (
        neutral,
        item.get("hue", 999),
        item.get("lightness", 0),
        item.get("colorName", ""),
        item.get("colorId", 0),
    )


def category_key(item: dict, category_name: dict[int, str], category_rank: dict[str, int]) -> tuple:
    category_id = item.get("categoryId")
    category = category_name.get(category_id, "zz unknown") if category_id is not None else "zz unknown"
    return category_rank.get(category, 500), category.lower()


def name_sort_key(item: dict) -> tuple:
    raw = item.get("name", "")
    name = clean_name(raw)
    dimension_match = DIM_RE.search(name)
    if dimension_match:
        prefix = name[: dimension_match.start()].strip(" ,-/")
        dimensions = tuple(number_value(value) for value in NUMBER_RE.findall(dimension_match.group(1)))
        suffix = name[dimension_match.end() :].strip(" ,-/")
    else:
        prefix = re.sub(NUMBER_RE, " ", name)
        prefix = re.sub(r"\s+", " ", prefix).strip(" ,-/")
        dimensions = tuple()
        suffix = name

    is_printed = 1 if PRINT_RE.search(raw) or "pr" in item.get("part", "") else 0
    normalized_suffix = PRINT_RE.sub(" ", suffix)
    normalized_suffix = re.sub(r"\s+", " ", normalized_suffix).strip()
    return (
        natural_chunks(prefix),
        dimensions,
        is_printed,
        natural_chunks(normalized_suffix),
        natural_chunks(raw),
    )


def clean_name(name: str) -> str:
    name = name.lower().replace("\u00b0", " degree ")
    name = re.sub(r"\[[^\]]*\]", " ", name)
    name = re.sub(r"\([^)]*\)", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def number_value(text: str) -> float:
    try:
        return float(Fraction(text))
    except (ValueError, ZeroDivisionError):
        return 9999.0


def natural_chunks(text: str) -> list:
    chunks = []
    for chunk in re.split(r"(\d+)", str(text).lower()):
        if not chunk:
            continue
        chunks.append(int(chunk) if chunk.isdigit() else chunk)
    return chunks


def write_outputs(payload: dict) -> None:
    DATA_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    DATA_JS.write_text(
        "window.REBRICKABLE_CHECKLIST_DATA = "
        + json.dumps(payload, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    HTML_FILE.write_text(APP_HTML, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
