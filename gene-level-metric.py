from __future__ import annotations

import datasets
import evaluate

from .gene_level_core import DEFAULT_SEGMENTS, DEFAULT_TYPES, compute_gff_metric, compute_python_metric

_DESCRIPTION = """
Gene-level metric for biologically rigorous exon-intron structure evaluation.

This implementation supports two entry points:

1. Python-like transcript matrices via `preds`, `targets`, and `mapping`.
2. GFF-based evaluation via `pred_gff` and `true_gff`.

The returned counts are grouped by the selected stratifier and reported separately for the selected segments.
"""

_KWARGS_DESCRIPTION = """
Python-like mode:
    preds:
        List of transcript arrays. Each transcript must be a 2D binary matrix with shape
        `(transcript_length, number_of_selected_segments)`.
    targets:
        Same structure as `preds`.
    mapping:
        List of strings with format:
        `transcript_id|gene_id|transcript_type|strand|genome|chrom|coord`

GFF mode:
    pred_gff:
        Path to a prediction GFF file or raw GFF text.
    true_gff:
        Path to a reference GFF file or raw GFF text.

Shared arguments:
    stratifier:
        One of `type`, `transcript_type`, `transcript`, `transcript_id`,
        `gene`, `gene_id`, `chromosome`, `strand`.
    types:
        Transcript types to include. Supported values: `mRNA`, `lnc_RNA`.
    segments:
        Segment types to score. Supported values: `exon`, `CDS`.

Returns:
    Dictionary with:
        - `mode`
        - `stratifier`
        - `types`
        - `segments`
        - `raw_result`
        - `rows`
        - `totals_by_segment`
        - `details`
"""

_CITATION = """
@misc{genatator_gene_level_metric,
  title        = {Gene-level metric for exon-intron structure evaluation},
  author       = {Community implementation},
  year         = {2026},
  howpublished = {Hugging Face Space}
}
"""


@evaluate.utils.file_utils.add_start_docstrings(_DESCRIPTION, _KWARGS_DESCRIPTION)
class GeneLevelMetric(evaluate.Metric):
    def _info(self) -> evaluate.MetricInfo:
        return evaluate.MetricInfo(
            description=_DESCRIPTION,
            citation=_CITATION,
            inputs_description=_KWARGS_DESCRIPTION,
            features=[
                datasets.Features(
                    {
                        "preds": datasets.Sequence(
                            datasets.Sequence(datasets.Value("int32"))
                        ),
                        "targets": datasets.Sequence(
                            datasets.Sequence(datasets.Value("int32"))
                        ),
                        "mapping": datasets.Value("string"),
                    }
                ),
                datasets.Features(
                    {
                        "pred_gff": datasets.Value("string"),
                        "true_gff": datasets.Value("string"),
                    }
                ),
            ],
            homepage="https://huggingface.co/spaces/shmelev/gene-level-metric",
            license="apache-2.0",
        )

    def _compute(
        self,
        preds=None,
        targets=None,
        mapping=None,
        pred_gff=None,
        true_gff=None,
        stratifier="type",
        types=DEFAULT_TYPES,
        segments=DEFAULT_SEGMENTS,
    ):
        if pred_gff is not None or true_gff is not None:
            if pred_gff is None or true_gff is None:
                raise ValueError("Both pred_gff and true_gff must be provided for GFF mode.")
            return compute_gff_metric(
                pred_gff=pred_gff,
                true_gff=true_gff,
                stratifier=stratifier,
                types=types,
                segments=segments,
            )

        if preds is None or targets is None or mapping is None:
            raise ValueError(
                "Provide either (preds, targets, mapping) for Python-like mode "
                "or (pred_gff, true_gff) for GFF mode."
            )

        return compute_python_metric(
            preds=preds,
            targets=targets,
            mapping=mapping,
            stratifier=stratifier,
            types=types,
            segments=segments,
        )
