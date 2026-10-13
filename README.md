# Science Arena Dashboard

Static reviewer dashboard for the sealed August 2026 release and the archived
earlier results. The default view contains IPhO, IChO, NBPhO and USAPhO 2026,
14 model routes, native-image/text input modes and four-competition macro
scores with 95% question-bootstrap intervals.

Build the sanitized data:

```bash
python3 scripts/sync_2026.py
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

The 2026 score and interval sources are small checksum-verified snapshots in
`scripts/sources/2026/`, pinned to commit
`c2a2acc4e311a8a7b0530de087fbf4e1b5cafe8c` of
[Science-Arena-code](https://github.com/stallone0000/Science-Arena-code).
The sync is offline, idempotent and adds no evaluation/API calls. It preserves
the existing archived scores and details. `scripts/build_site_data.py` is the
legacy archive builder and requires the original pre-release workspace.

Archived NBPhO/USAPhO inputs are from **2025**; the older site incorrectly
labelled them 2026. They are separate from the new sealed 2026 cells. The
archived international scores and human references remain in their own tab.
No absence of training exposure is inferred from model release timing.

The 2026 view displays the released aggregate scores. Question images, visible
model answers and rubric-judge ledgers stay in the
[GitHub Release](https://github.com/stallone0000/Science-Arena-code/releases/tag/cr-final-2026-08-31),
linked from the dashboard. They are not bundled into the static site or fetched
automatically by its builder. The 95% intervals describe whole-question
sampling sensitivity, not generation or judge variance.

For a compact local checkout, keep deployed archived details/images on GitHub:

```bash
git clone --filter=blob:none --depth 1 --sparse https://github.com/stallone0000/Science-Arena.git
cd Science-Arena
git sparse-checkout set --no-cone '/*' '!/static/' '/static/css/' '/static/js/' '/static/assets/' '/static/data/manifest.json' '/static/data/fallback.html'
```

This retains code, small score data and UI assets. The two archived tabs need
`static/data/details/` and `static/data/assets/` for local problem browsing;
restore them with `git sparse-checkout disable` when required. Render uses the
full repository, so this local setting does not affect the deployed site.
