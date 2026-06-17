# Rebrickable Parts Checklist

This project builds a local checklist from every CSV in the `csv/` folder.

Each input CSV must use this header:

```csv
Part,Color,Quantity
```

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

Open `rebrickable-checklist.html` in a browser to use the checklist. Counts and checks are saved by the browser.
