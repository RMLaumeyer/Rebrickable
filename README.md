# Rebrickable Parts Checklist

An interactive LEGO parts checklist built from every inventory CSV in `csv/`. Each part/color combination has an image, required quantity, owned counter, and completion checkbox.

## Quick start

1. Put inventory CSV files directly in `csv/`.
2. Open PowerShell in this project folder and run `python generate_checklist.py` (or `py generate_checklist.py`).
3. Double-click `rebrickable-checklist.html` to open it in Chrome or Edge.
4. After regenerating, refresh the page with `Ctrl+F5`.

The generator needs Python 3 and uses only its standard library. No pip packages, API key, or web server are required. Internet access is needed for the first metadata download and uncached images. Once metadata is cached, generation can run offline.

## Input format

Each input CSV must use this header:

```csv
Part,Color,Quantity
3001,4,2
3023,0,6
3069bpr0030,72,1
```

Use Rebrickable part numbers and numeric Rebrickable color IDs. Quantities should be positive whole numbers. Save files as UTF-8 without a byte-order mark (BOM), using the exact header names above.

The generator reads every `*.csv` directly inside `csv/`; it does not search subfolders, the project root, or `Old/`. Matching part/color rows have their quantities added, including duplicates across files. For example, quantities of 2 and 3 produce one tile requiring 5.

To add an inventory, add a CSV and regenerate. To replace an inventory, move its previous CSV out of `csv/` first so both copies are not counted. Removing a file removes its contribution from the next checklist.

## Regenerating

To regenerate the checklist after adding CSV files:

```powershell
py generate_checklist.py
```

If `py` is not available, run it with any Python 3 install:

```powershell
python generate_checklist.py
```

The generator:

- reads every `*.csv` in `csv/`
- combines duplicate `Part + Color` rows by adding quantities
- downloads Rebrickable public metadata into `.rebrickable-cache/`
- rebuilds `rebrickable-checklist-data.json`
- rebuilds `rebrickable-checklist-data.js`
- rewrites `rebrickable-checklist.html`

Later runs reuse cached metadata. To download fresh metadata and rebuild:

```powershell
python generate_checklist.py --refresh-cache
```

## Checklist controls

- Use `+`, `-`, or the number field to update your owned count.
- A tile checks automatically when its count reaches the required quantity.
- Checking a tile sets its count to the requirement; unchecking sets it to zero.
- Search by part number, name, or color name.
- **Missing** shows zero-owned items. **Partial** shows items with some but fewer than required. **Complete** shows items at or above the requirement.
- The overall piece counter counts toward requirements and excludes surplus pieces.
- **Export** downloads a CSV report of all current items, including required quantities, owned counts, and completion status.
- **Reset** clears all saved counts after confirmation, including items hidden by filters.

## Saved progress

Counts are saved automatically in browser local storage under `rebrickable-checklist-progress-v1`, keyed by part number and color ID. Progress is not written to the HTML, input CSVs, or generated files, and OneDrive does not synchronize that browser storage.

Regenerating or sorting does not clear browser storage. Matching part/color IDs retain their counts in the same storage context; changed requirements can change whether they are complete.

Use the same browser profile and file location to continue. Clearing browser data, switching browsers, private browsing, or moving the HTML can make progress unavailable. Local-file storage behavior depends on the browser.

Export periodically for a readable record. There is currently no progress-import feature. Exported reports use a different schema from inventory inputs and should not be placed in `csv/`.

## Sorting and images

Colors are grouped by hue, with low-saturation colors placed after other colors. Within each color, parts use a custom category sequence, family/name, numeric dimensions, and variant details. For example, `Plate 1 x 2` comes before `Plate 1 x 10`.

This is a custom Rebrickable-inspired sort, not a verified reproduction of Rebrickable's or BrickLink's exact ordering algorithm.

Names, colors, categories, and element IDs come from Rebrickable public metadata. Images load from Rebrickable's CDN, with fallback URLs and several manually configured aliases. Some aliases show a different mold, an unprinted base piece, or a different color. Check the part number, name, and color label when identifying a piece. Sticker sheets and other unavailable images may remain blank. The generator does not automatically check new images for availability.

## Project files

| Path | Purpose |
| --- | --- |
| `csv/` | Active inventory inputs |
| `generate_checklist.py` | Merging, metadata enrichment, sorting, and HTML generation |
| `.rebrickable-cache/` | Downloaded metadata reused between runs |
| `rebrickable-checklist.html` | Generated page to open in a browser |
| `rebrickable-checklist-data.js` | Generated data for opening without a server |
| `rebrickable-checklist-data.json` | Generated JSON data and HTTP fallback |
| `rebrickable-checklist.js` | Counters, filters, storage, and export |
| `rebrickable-checklist.css` | Layout and styling |
| `Old/` | Archived files, when present; ignored by the generator |

The generator overwrites the HTML and both data files. Make persistent HTML edits in `APP_HTML` inside `generate_checklist.py`. Edit application JavaScript and CSS directly; generation does not rewrite them. Keep the HTML, CSS, application JavaScript, and data JavaScript together when moving the app.

## Troubleshooting

- **Python not recognized:** try `py generate_checklist.py`, or run the script with your Python executable's full path.
- **No CSV files found:** put at least one inventory CSV directly in `csv/`.
- **Missing columns:** check exact header spelling and UTF-8 encoding without a BOM.
- **Invalid integer:** check for blank cells or non-integer values in `Color` and `Quantity`.
- **Unexpected totals:** inspect all active CSVs; overlapping inventories add together and archived files are excluded.
- **Download or corrupt cache error:** check your connection and rerun with `--refresh-cache`.
- **Old data displayed:** regenerate successfully, then press `Ctrl+F5`.
- **Missing images:** check your connection; some CDN images are unavailable even with valid inventory data.

This independent project is not an official LEGO, BrickLink, or Rebrickable application.
