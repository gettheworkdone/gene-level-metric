---
title: Gene-level Metric
emoji: 🧬
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Gene-level exon-intron metric + live leaderboard
tags:
  - evaluate
  - genomics
  - metric
  - bioinformatics
---

# Gene-level Metric + Live Leaderboard

This Space now includes:

1. **Metric usage page** (Evaluate API + interactive calculator).
2. **Live leaderboard page** that computes scores from prediction files automatically.

## Leaderboard pipeline

When you click **Start / Rebuild leaderboard** in the UI, backend will:

1. Clone/pull: `https://github.com/alexeyshmelev/genatator-leaderboard-predictions.git`.
2. Enter `predictions/` and process all `*.gff` files.
3. Compute gene-level metric for each file.
4. Compute BUSCO metric for each file.
5. Stream progress and partial results via `/api/leaderboard/status`.

## Required local assets

Put these files into `leaderboard_required_files/`:

- `true.gff`
- `reference.fa`
- `lineage/` (BUSCO offline lineage directory)

See `leaderboard_required_files/README.md`.

## BUSCO installation

The Docker image installs Miniconda and BUSCO 5.7.1 via:

```bash
conda install -c bioconda busco==5.7.1
```

BUSCO is run in offline proteins mode for each model.

## Local run

```bash
docker build -t gene-level-metric .
docker run -p 7860:7860 gene-level-metric
```

Open `http://localhost:7860`.
