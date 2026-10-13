# Published 2026 per-question artifact coverage

Checked on 2026-10-13 against every asset of `cr-final-2026-08-31` in
`stallone0000/Science-Arena-code` (seven checksum-verified assets).
[Full cloud inventory](https://github.com/stallone0000/Science-Arena/actions/runs/38364242109).
The website repository has no separate releases; no other Science/Arena
repository was present in the authenticated account's repository listing.

| Competition | Published source | Detail coverage |
| --- | --- | --- |
| IPhO 2026 | `ipho2026_table6_qonly_gemini31_frozen_formal_20260829` | Present; vision records are linked to the corrected earlier run, text records are regular files |
| IChO 2026 | `icho2026_table6_qonly_gemini31_frozen_v2_formal_20260829` | Present; vision reuse links resolve through the scientific-correction run |
| NBPhO 2026 | `nbpho2026_table6_qonly_gemini31_frozen_v2_judge_v8_materialized_full_fresh_20260829` | Final directory absent from released assets |
| USAPhO 2026 | `usapho2026_table6_qonly_gemini31_frozen_v2_judge_v5_full_fresh_20260829` | Final directory absent from released assets |

The NBPhO/USAPhO raw archive actually contains:

```
experiments/2026_reval/runs/nbpho2026_table6_qonly_gemini31_frozen_v2_formal_20260829
experiments/2026_reval/runs/usapho2026_table6_qonly_gemini31_frozen_v2_formal_20260829
```

These are earlier runs. For example, the earlier NBPhO aggregate has GPT-5.5
at 57.5/72; the published final table has 59.2/72. Neither renaming an earlier
run nor rescaling its item scores can recover the missing final judgments.

The exporter checks source-archive SHA-256, exact frozen item SHA-256, original
PNG hashes when declared, terminal identities, input modes, raw point caps,
criterion sums and weighted competition totals. The archive's aggregate JSON
serialization can differ from the original analysis snapshot's byte hash;
all 14 aggregate values and all reconstructed terminal totals must still match
the checksum-bound published score table. The public outputs are a field
allowlist and omit raw provider responses, hidden reasoning and personal paths.

The site exposes fully checked available runs. Missing final-run detail is
explicitly labelled; published macro/competition scores are retained. The
missing runs are recorded in `static/data/2026/build_report.json` and the small
detail index. The default builder refuses a missing sealed run; the CI input
`allow_missing_runs` permits publishing verified available competitions while
recording these gaps, never substituting older item grades.

To complete NBPhO/USAPhO details, recover their final solver and judge terminal
trees plus aggregates, upload them as a new immutable release asset, bind its
size/SHA-256 in the source manifest, and rerun the workflow. A new model/judge
rerun would produce a new experiment, not recreate the missing frozen records.
