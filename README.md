---
title: gene-level-metric
emoji: 🧬
colorFrom: green
colorTo: blue
sdk: docker
pinned: false
short_description: Gene-level metric playground
---

# GENATATOR Gene-level Metric

A Docker-based Hugging Face Space with:

- a **single-page React + Material UI interface**
- a **FastAPI backend** that computes the metric in Python
- a **playground** for manual inputs
- built-in **example presets**

## What the app does

The Space computes exact transcript-level agreement between predicted and target binary masks.

- `0` = intron / non-exonic position
- `1` = exon or CDS position

Optional modes:

- **splice filter**: keeps only internal exons with allowed splice motifs
- **CDS heuristics**: converts exon predictions into CDS predictions via longest ORF search

## Mapping format

Each mapping entry must follow:

```text
chrom|gene_type|gene_id|transcript_id|strand|coord
```

Example:

```text
chr1|mRNA|GENE0001|TX0001|+|1-12
```

## Local run

```bash
docker build -t genatator-gene-level-metric .
docker run -p 7860:7860 genatator-gene-level-metric
```

Then open `http://localhost:7860`.
