# Required files for leaderboard pipeline

Place required assets here before running leaderboard build:

- `true.gff` — reference annotation GFF.
- `reference.fa` — reference genome FASTA matching `true.gff`.
- `lineage/` — BUSCO lineage database folder (offline mode).

The backend will refuse to start the pipeline if these are missing.
