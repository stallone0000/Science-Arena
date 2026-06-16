# Science Arena Anonymous Review Site

Static reviewer dashboard for the current Science Arena result artifacts.

Build the sanitized data:

```bash
python scripts/build_site_data.py
```

The generated `static/data/` directory is committed/deployed with the site. A standalone Render static site can therefore use an empty build command, or the included `render.yaml` prebuilt-data check.

Serve locally from this directory:

```bash
python -m http.server 4173
```

The page is intentionally anonymous: it contains no author or institution names, and generated public data omits local absolute paths.

Primary generated files:

- `static/data/manifest.json`
- `static/data/details/<benchmark>/<model>.json`

The current data source is the 2026-05-26 text-only interleaved rebuild, with saved official objective-key scoring for IBO 2023.
