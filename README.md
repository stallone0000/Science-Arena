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

The 2026 view displays the released aggregate scores. Available sealed runs
also have clickable question cells with visible model answers, criterion
scores/evidence, the frozen native/text question, reference answer, rubric and
original question/solution page PNGs. Each model's detail JSON is fetched only
when a cell is selected; shared question material and images are stored once.
Failed requests expose a Retry button.

`Build 2026 problem details` is a manually dispatched GitHub Actions workflow.
It downloads and checksums the original
[Release assets](https://github.com/stallone0000/Science-Arena-code/releases/tag/cr-final-2026-08-31)
on a temporary GitHub runner, resolves archived record reuse links, verifies
frozen item/image hashes, and reconstructs each displayed competition total
from item scores with the original sequence weights. It publishes only the
visible-answer/feedback fields and needed PNGs to `static/data/2026/`.
Provider wire payloads, hidden reasoning and personal filesystem paths are
not exported. No model inference is performed.

The ordinary `sync_2026.py` rebuild stays offline and uses only the small
`static/data/2026/index.json`. It never downloads the large archives or the
per-model answer files. The 95% intervals describe whole-question sampling
sensitivity, not generation or judge variance.

Current release coverage: **IPhO and IChO 2026** support all 14 models' question
details. The release does not contain the final NBPhO v8 or USAPhO v5 run
directories bound by the published analysis manifest. Those two competitions
retain the published totals and explicitly state that final per-question
records are unavailable; earlier grades are not substituted. See
[the coverage audit](docs/2026_RELEASE_COVERAGE.md).

For a compact local checkout, keep deployed archived details/images on GitHub:

```bash
git clone --filter=blob:none --depth 1 --sparse https://github.com/stallone0000/Science-Arena.git
cd Science-Arena
git sparse-checkout set --no-cone '/*' '!/static/' '/static/css/' '/static/js/' '/static/assets/' '/static/data/manifest.json' '/static/data/fallback.html' '/static/data/2026/index.json' '/static/data/2026/build_report.json'
```

This retains code, small score/detail indexes and UI assets. For local problem
browsing, answer JSONs and PNGs can be served from the deployed site; a full
offline view needs the omitted `static/data/2026/` files or the legacy
`static/data/details/` and `static/data/assets/`. Restore them with
`git sparse-checkout disable` when required. Render uses the full repository,
so this local setting does not affect the deployed site.
