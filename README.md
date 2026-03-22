---
title: Gene-level Metric
emoji: 🧬
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Gene-level exon-intron metric
tags:
  - evaluate
  - genomics
  - metric
  - bioinformatics
---

# Gene-level Metric

This repository contains a Hugging Face Space and an Evaluate-compatible metric for biologically rigorous assessment of exon–intron structure.

## Two supported modes

### 1. Python-like mode

Use transcript-wise binary matrices:

- `preds`: list of transcript arrays
- `targets`: list of transcript arrays
- `mapping`: list of strings in the format  
  `transcript_id|gene_id|transcript_type|strand|genome|chrom|coord`
- `stratifier`: one of `type`, `transcript_type`, `transcript`, `transcript_id`, `gene`, `gene_id`, `chromosome`, `strand`
- `types`: subset of `["mRNA", "lnc_RNA"]`
- `segments`: subset of `["exon", "CDS"]`

Each transcript array must have shape:

```text
(transcript_length_in_nt, number_of_selected_segments)
```

The column order must match `segments`.

Example:

```python
import evaluate

metric = evaluate.load("shmelev/gene-level-metric")

result = metric.compute(
    preds=[
        [
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 0],
            [1, 1],
            [1, 1],
            [0, 0],
            [0, 0],
        ]
    ],
    targets=[
        [
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 0],
            [1, 1],
            [1, 1],
            [0, 0],
            [0, 0],
        ]
    ],
    mapping=[
        "TX0001|GENE0001|mRNA|+|GRCh38|chr1|1-8",
    ],
    stratifier="type",
    types=["mRNA", "lnc_RNA"],
    segments=["exon", "CDS"],
)
```

### 2. GFF mode

Use:

- `pred_gff`: path to a prediction GFF file or raw GFF text
- `true_gff`: path to a reference GFF file or raw GFF text
- `stratifier`, `types`, `segments`: same as above

Reference GFF requirements:

- standard 9-column GFF
- transcript rows of type `mRNA` and/or `lnc_RNA`
- `gene` rows with `ID`
- transcript rows with `ID` and `Parent`
- exon/CDS rows with `Parent=<transcript_id>`

Prediction GFF requirements in this implementation:

- standard 9-column GFF
- only `exon` / `CDS` rows are used
- `seqid` must equal the transcript id from the reference annotation
- coordinates are interpreted in transcript-relative space

Example:

```python
import evaluate

metric = evaluate.load("shmelev/gene-level-metric")

result = metric.compute(
    pred_gff="predictions.gff",
    true_gff="reference.gff",
    stratifier="type",
    types=["mRNA", "lnc_RNA"],
    segments=["exon", "CDS"],
)
```

## What the metric returns

The metric returns counts grouped by the chosen `stratifier`. Each category contains one count per selected segment.

Example output:

```python
{
    "raw_result": {
        "lnc_RNA": [0, 0],
        "mRNA": [1, 1],
    },
    "segments": ["exon", "CDS"],
    "stratifier": "type",
}
```

## Local run

```bash
docker build -t gene-level-metric .
docker run -p 7860:7860 gene-level-metric
```

Then open `http://localhost:7860`.
