# Required files for leaderboard pipeline

Place required assets here before running leaderboard build:

- `chr20.gff` — reference annotation GFF.
- `Hs_NC_060944.1.fa` — reference FASTA matching the annotation.
- `lineage/mammalia_odb10/` — BUSCO lineage directory (offline mode).

The backend starts leaderboard automatically at app startup and will fail if these are missing.
