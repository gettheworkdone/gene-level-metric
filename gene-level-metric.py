from __future__ import annotations

import datasets
import evaluate

from .gene_level_core import DEFAULT_SEGMENTS, DEFAULT_TYPES, compute_gff_metric, compute_python_metric

_DESCRIPTION = """
Gene-level metric for biologically rigorous exon-intron structure evaluation.

Load the metric once with `evaluate.load("shmelev/gene-level-metric")`, then call one of the two named entry points:

1. `compute_gene_level_python(...)` for transcript-wise binary matrices.
2. `compute_gene_level_gff(...)` for GFF-based evaluation.

The returned counts are grouped by the selected stratifier and reported separately for the selected segments.
"""

_KWARGS_DESCRIPTION = """
Named entry points:
    metric.compute_gene_level_python(...)
        preds:
            List of transcript arrays. Each transcript must be a 2D binary matrix with shape
            `(transcript_length, number_of_selected_segments)`.
        targets:
            Same structure as `preds`.
        mapping:
            List of strings with format:
            `transcript_id|gene_id|transcript_type|strand|genome|chrom|coord`
        stratifier:
            One of `type`, `transcript_type`, `transcript`, `transcript_id`,
            `gene`, `gene_id`, `chromosome`, `strand`.
        types:
            Transcript types to include. Supported values: `mRNA`, `lnc_RNA`.
        segments:
            Segment types to score. Supported values: `exon`, `CDS`.

    metric.compute_gene_level_gff(...)
        pred_gff:
            Path to a prediction GFF file or raw GFF text.
        true_gff:
            Path to a reference GFF file or raw GFF text.
        stratifier:
            Same accepted values as above.
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

    def compute(self, *args, **kwargs):  # pragma: no cover - user guidance path
        """Unsupported shortcut for this metric. Use one of the named entry points instead.

        See `compute_gene_level_python(...)` and `compute_gene_level_gff(...)`.
        """
        raise ValueError(
            "This metric exposes named entry points. Use `compute_gene_level_python(...)` "
            "or `compute_gene_level_gff(...)` after `evaluate.load(...)`."
        )

    def compute_gene_level_python(
        self,
        preds,
        targets,
        mapping,
        stratifier="type",
        types=DEFAULT_TYPES,
        segments=DEFAULT_SEGMENTS,
    ):
        """Compute the gene-level metric from transcript-wise binary matrices."""
        return compute_python_metric(
            preds=preds,
            targets=targets,
            mapping=mapping,
            stratifier=stratifier,
            types=types,
            segments=segments,
        )

    def compute_gene_level_gff(
        self,
        pred_gff,
        true_gff,
        stratifier="type",
        types=DEFAULT_TYPES,
        segments=DEFAULT_SEGMENTS,
    ):
        """Compute the gene-level metric from GFF inputs."""
        return compute_gff_metric(
            pred_gff=pred_gff,
            true_gff=true_gff,
            stratifier=stratifier,
            types=types,
            segments=segments,
        )
