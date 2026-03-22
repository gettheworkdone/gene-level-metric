from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, Sequence, Union

import numpy as np
import pandas as pd

PathLike = Union[str, Path]

DEFAULT_TYPES = ["mRNA", "lnc_RNA"]
DEFAULT_SEGMENTS = ["exon", "CDS"]

PYTHON_EXAMPLE = {
    "preds": [
        [
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 0],
            [1, 1],
            [1, 1],
            [0, 0],
            [0, 0],
        ],
        [
            [0, 0],
            [1, 0],
            [1, 0],
            [0, 0],
            [0, 0],
            [0, 0],
            [1, 0],
            [1, 0],
            [0, 0],
            [0, 0],
        ],
    ],
    "targets": [
        [
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 0],
            [1, 1],
            [1, 1],
            [0, 0],
            [0, 0],
        ],
        [
            [0, 0],
            [1, 0],
            [1, 0],
            [1, 0],
            [0, 0],
            [0, 0],
            [1, 0],
            [1, 0],
            [0, 0],
            [0, 0],
        ],
    ],
    "mapping": [
        "TX0001|GENE0001|mRNA|+|GRCh38|chr1|1-8",
        "TX0002|GENE0002|lnc_RNA|-|GRCh38|chr5|1-10",
    ],
    "stratifier": "type",
    "types": ["mRNA", "lnc_RNA"],
    "segments": ["exon", "CDS"],
}


def _segments_to_lists(segments: Iterable[tuple[int, int]]) -> list[list[int]]:
    return [[int(start), int(end)] for start, end in sorted(segments)]


class GeneLevelEvaluator:
    GFF_COLUMNS = [
        "seqid",
        "source",
        "type",
        "start",
        "end",
        "score",
        "strand",
        "phase",
        "attributes",
    ]

    PART_ALIASES = {
        "exon": "exon",
        "cds": "CDS",
    }

    TRANSCRIPT_TYPE_ALIASES = {
        "mrna": "mRNA",
        "lncrna": "lnc_RNA",
        "lnc_rna": "lnc_RNA",
        "lnc-rna": "lnc_RNA",
    }

    SUPPORTED_STRATIFIERS = {
        "chromosome",
        "transcript_type",
        "type",
        "transcript_id",
        "transcript",
        "strand",
        "gene_id",
        "gene",
    }

    def gene_level_gff(
        self,
        pred_gff: Union[PathLike, pd.DataFrame],
        true_gff: Union[PathLike, pd.DataFrame],
        stratifier: str,
        types: Sequence[str] = ("mRNA", "lnc_RNA"),
        segments: Sequence[str] = ("exon", "CDS"),
    ) -> Dict[Any, list[int]]:
        output = self.gene_level_gff_detailed(
            pred_gff=pred_gff,
            true_gff=true_gff,
            stratifier=stratifier,
            types=types,
            segments=segments,
        )
        return output["raw_result"]

    def gene_level_gff_detailed(
        self,
        pred_gff: Union[PathLike, pd.DataFrame],
        true_gff: Union[PathLike, pd.DataFrame],
        stratifier: str,
        types: Sequence[str] = ("mRNA", "lnc_RNA"),
        segments: Sequence[str] = ("exon", "CDS"),
    ) -> Dict[str, Any]:
        true_df = self._read_gff(true_gff, mode="true")
        pred_df = self._read_gff(pred_gff, mode="pred")

        types = tuple(self._normalize_transcript_type(x) for x in types)
        segments = tuple(self._normalize_part(x) for x in segments)

        self._validate_stratifier(stratifier)
        self._validate_segments(segments)

        transcript_meta = self._build_transcript_meta(true_df, types=types)
        pred_df_segments = pred_df[pred_df["type"].isin(segments)].copy()

        result_sets = self._initialize_result_sets(
            transcript_meta=transcript_meta,
            stratifier=stratifier,
            segments=segments,
        )

        details: list[dict[str, Any]] = []

        for transcript_id in transcript_meta.index.tolist():
            meta = transcript_meta.loc[transcript_id]
            transcript_type = meta["transcript_type"]
            gene_id = meta["gene_id"]
            transcript_start = int(meta["start"])
            category = self._get_stratifier_value(meta, stratifier)

            transcript_true_df_segments = true_df[true_df["Parent"] == transcript_id].copy()
            transcript_pred_df_segments = pred_df_segments[pred_df_segments["ID"] == transcript_id].copy()

            detail = {
                "transcript_id": transcript_id,
                "gene_id": gene_id,
                "transcript_type": transcript_type,
                "strand": str(meta["strand"]),
                "seqid": str(meta["seqid"]),
                "coord": f"{int(meta['start']) + 1}-{int(meta['end'])}",
                "length": int(meta["end"] - meta["start"]),
                "category": category,
                "segments": {},
            }

            for seg_idx, segment in enumerate(segments):
                true_segments_set = self.search_segments(
                    transcript_df_segments=transcript_true_df_segments,
                    segment=segment,
                    transcript_start=transcript_start,
                )

                pred_segments_set = self.search_segments(
                    transcript_df_segments=transcript_pred_df_segments,
                    segment=segment,
                    transcript_start=0,
                )

                match: bool | None
                if len(true_segments_set) == 0:
                    match = None
                else:
                    if transcript_type != "mRNA" and segment == "CDS":
                        raise ValueError("CDS in the non-protein-coding gene")
                    match = pred_segments_set == true_segments_set
                    if match:
                        if self._normalize_stratifier_name(stratifier) == "transcript_id":
                            result_sets[category][seg_idx].add(transcript_id)
                        else:
                            result_sets[category][seg_idx].add(gene_id)

                detail["segments"][segment] = {
                    "predicted": _segments_to_lists(pred_segments_set),
                    "target": _segments_to_lists(true_segments_set),
                    "match": match,
                }

            details.append(detail)

        raw_result = {
            category: [len(segment_set) for segment_set in per_segment_sets]
            for category, per_segment_sets in result_sets.items()
        }
        return self._pack_output(
            mode="gff",
            raw_result=raw_result,
            stratifier=stratifier,
            types=list(types),
            segments=list(segments),
            details=details,
        )

    def _read_gff(
        self,
        gff: Union[PathLike, pd.DataFrame],
        mode: str,
    ) -> pd.DataFrame:
        if isinstance(gff, pd.DataFrame):
            df = gff.copy()
        elif isinstance(gff, (str, Path)):
            if isinstance(gff, Path):
                path = gff
                df = pd.read_csv(
                    path,
                    sep="\t",
                    names=self.GFF_COLUMNS,
                    header=None,
                    comment="#",
                    dtype=str,
                )
            else:
                text = str(gff)
                if self._looks_like_gff_text(text):
                    df = pd.read_csv(
                        StringIO(text),
                        sep="\t",
                        names=self.GFF_COLUMNS,
                        header=None,
                        comment="#",
                        dtype=str,
                    )
                else:
                    path = Path(text)
                    if not path.exists():
                        raise ValueError("GFF path does not exist and no inline GFF content was detected.")
                    df = pd.read_csv(
                        path,
                        sep="\t",
                        names=self.GFF_COLUMNS,
                        header=None,
                        comment="#",
                        dtype=str,
                    )
        else:
            raise ValueError("Unsupported GFF input type.")

        if df.empty:
            raise ValueError("GFF is empty")

        df["start"] = pd.to_numeric(df["start"], errors="raise").astype(int) - 1
        df["end"] = pd.to_numeric(df["end"], errors="raise").astype(int)

        attrs = df["attributes"].fillna("").map(self._parse_attributes)
        attrs_df = pd.DataFrame(attrs.tolist())
        df = pd.concat([df.reset_index(drop=True), attrs_df.reset_index(drop=True)], axis=1)

        if mode == "true":
            if "ID" not in df.columns or "Parent" not in df.columns:
                raise ValueError("true GFF must contain ID and Parent in attributes")
        elif mode == "pred":
            df["ID"] = df["seqid"]
        else:
            raise ValueError("mode must be 'true' or 'pred'")

        return df

    @staticmethod
    def _looks_like_gff_text(text: str) -> bool:
        if "\n" in text or "\t" in text:
            return True
        stripped = text.strip()
        return stripped.startswith("#") or stripped.count(";") >= 1 or stripped.count("\t") >= 8

    @staticmethod
    def _parse_attributes(attr: str) -> Dict[str, str]:
        result: Dict[str, str] = {}
        if not isinstance(attr, str) or not attr.strip():
            return result

        for field in attr.strip().split(";"):
            field = field.strip()
            if not field:
                continue

            if "=" in field:
                key, value = field.split("=", 1)
            elif " " in field:
                key, value = field.split(" ", 1)
                value = value.strip().strip('"')
            else:
                key, value = field, ""

            result[key.strip()] = value.strip()

        return result

    def _build_transcript_meta(
        self,
        true_df: pd.DataFrame,
        types: Sequence[str],
    ) -> pd.DataFrame:
        gene_ids = true_df.loc[true_df["type"] == "gene", "ID"].dropna().unique().tolist()

        transcript_rows = true_df[
            true_df["Parent"].isin(gene_ids) & true_df["type"].isin(types)
        ].copy()

        if transcript_rows.empty:
            raise ValueError("No transcript rows found for selected transcript types")

        records = []

        for _, row in transcript_rows.iterrows():
            transcript_id = str(row["ID"])
            gene_id = str(row["Parent"])
            transcript_type = self._normalize_transcript_type(row["type"])

            rec = row.to_dict()
            rec["transcript_id"] = transcript_id
            rec["gene_id"] = gene_id
            rec["transcript_type"] = transcript_type
            records.append(rec)

        out = pd.DataFrame(records)
        out = out.drop_duplicates(subset=["transcript_id"]).set_index("transcript_id", drop=False)
        return out

    def _initialize_result_sets(
        self,
        transcript_meta: pd.DataFrame,
        stratifier: str,
        segments: Sequence[str],
    ) -> Dict[Any, list[set[str]]]:
        keys = self._collect_all_stratifier_keys(transcript_meta, stratifier)
        return {key: [set() for _ in segments] for key in keys}

    def _collect_all_stratifier_keys(
        self,
        transcript_meta: pd.DataFrame,
        stratifier: str,
    ) -> list[Any]:
        stratifier = self._normalize_stratifier_name(stratifier)

        if stratifier == "gene_id":
            keys = transcript_meta["gene_id"].dropna().unique().tolist()
        elif stratifier == "transcript_id":
            keys = transcript_meta["transcript_id"].dropna().unique().tolist()
        elif stratifier == "transcript_type":
            keys = transcript_meta["transcript_type"].dropna().unique().tolist()
        elif stratifier == "seqid":
            keys = transcript_meta["seqid"].dropna().unique().tolist()
        elif stratifier == "strand":
            keys = transcript_meta["strand"].dropna().unique().tolist()
        else:
            raise KeyError(f"Unsupported stratifier: {stratifier!r}")

        return sorted(keys)

    def _get_stratifier_value(
        self,
        transcript_row: pd.Series,
        stratifier: str,
    ) -> Any:
        stratifier = self._normalize_stratifier_name(stratifier)

        if stratifier == "gene_id":
            value = transcript_row["gene_id"]
        elif stratifier == "transcript_id":
            value = transcript_row["transcript_id"]
        elif stratifier == "transcript_type":
            value = transcript_row["transcript_type"]
        elif stratifier == "seqid":
            value = transcript_row["seqid"]
        elif stratifier == "strand":
            value = transcript_row["strand"]
        else:
            raise KeyError(f"Unsupported stratifier: {stratifier!r}")

        if pd.isna(value):
            return "<NA>"
        return value

    def _normalize_stratifier_name(self, stratifier: str) -> str:
        alias = {
            "type": "transcript_type",
            "transcript_type": "transcript_type",
            "transcript_id": "transcript_id",
            "transcript": "transcript_id",
            "gene_id": "gene_id",
            "gene": "gene_id",
            "chromosome": "seqid",
            "strand": "strand",
        }
        if stratifier not in alias:
            raise KeyError(
                f"Unsupported stratifier={stratifier!r}. "
                f"Supported: {sorted(self.SUPPORTED_STRATIFIERS)}"
            )
        return alias[stratifier]

    def _validate_stratifier(self, stratifier: str) -> None:
        self._normalize_stratifier_name(stratifier)

    def search_segments(
        self,
        transcript_df_segments: pd.DataFrame,
        segment: str,
        transcript_start: int,
    ) -> set[tuple[int, int]]:
        segment_df = transcript_df_segments[transcript_df_segments["type"] == segment]
        starts_segment = np.array(segment_df["start"].tolist(), dtype=int)
        ends_segment = np.array(segment_df["end"].tolist(), dtype=int)
        return set(zip(starts_segment - transcript_start, ends_segment - transcript_start))

    def _normalize_part(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        key = value.strip()
        return self.PART_ALIASES.get(key.lower(), key)

    def _normalize_transcript_type(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        key = value.strip()
        return self.TRANSCRIPT_TYPE_ALIASES.get(key.lower(), key)

    def _validate_segments(self, segments: Sequence[str]) -> None:
        allowed = {"exon", "CDS"}
        unknown = [seg for seg in segments if seg not in allowed]
        if unknown:
            raise ValueError(f"Unsupported segments: {unknown}. Allowed: {sorted(allowed)}")

    def gene_level_python(
        self,
        preds: Sequence[np.ndarray],
        targets: Sequence[np.ndarray],
        mapping: Sequence[str],
        stratifier: str,
        types: Sequence[str] = ("mRNA", "lnc_RNA"),
        segments: Sequence[str] = ("exon", "CDS"),
    ) -> Dict[Any, list[int]]:
        output = self.gene_level_python_detailed(
            preds=preds,
            targets=targets,
            mapping=mapping,
            stratifier=stratifier,
            types=types,
            segments=segments,
        )
        return output["raw_result"]

    def gene_level_python_detailed(
        self,
        preds: Sequence[np.ndarray],
        targets: Sequence[np.ndarray],
        mapping: Sequence[str],
        stratifier: str,
        types: Sequence[str] = ("mRNA", "lnc_RNA"),
        segments: Sequence[str] = ("exon", "CDS"),
    ) -> Dict[str, Any]:
        types = tuple(self._normalize_transcript_type(x) for x in types)
        segments = tuple(self._normalize_part(x) for x in segments)

        self._validate_stratifier(stratifier)
        self._validate_segments(segments)

        if not (len(preds) == len(targets) == len(mapping)):
            raise ValueError("preds, targets and mapping must have the same number of transcripts")

        meta_records = [self._parse_mapping_record(record) for record in mapping]
        meta_df = pd.DataFrame(meta_records)

        if meta_df.empty:
            return self._pack_output(
                mode="python",
                raw_result={},
                stratifier=stratifier,
                types=list(types),
                segments=list(segments),
                details=[],
            )

        meta_df["transcript_type"] = meta_df["transcript_type"].map(self._normalize_transcript_type)
        keep_mask = meta_df["transcript_type"].isin(types)
        kept_indices = np.where(keep_mask.to_numpy())[0]
        meta_df = meta_df.loc[keep_mask].copy()

        if meta_df.empty:
            return self._pack_output(
                mode="python",
                raw_result={},
                stratifier=stratifier,
                types=list(types),
                segments=list(segments),
                details=[],
            )

        result_sets = self._initialize_result_sets_from_mapping(
            meta_df=meta_df,
            stratifier=stratifier,
            segments=segments,
        )

        n_expected_segments = len(segments)
        details: list[dict[str, Any]] = []

        for idx in kept_indices:
            pred_arr = np.asarray(preds[idx])
            target_arr = np.asarray(targets[idx])
            meta = meta_records[idx]

            transcript_type = self._normalize_transcript_type(meta["transcript_type"])
            transcript_id = meta["transcript_id"]
            gene_id = meta["gene_id"]

            if pred_arr.ndim != 2 or target_arr.ndim != 2:
                raise ValueError(
                    f"preds[{idx}] and targets[{idx}] must be 2D arrays with shape "
                    f"(transcript_len, n_segments)"
                )

            if pred_arr.shape != target_arr.shape:
                raise ValueError(
                    f"Shape mismatch for transcript {transcript_id}: "
                    f"pred {pred_arr.shape} != target {target_arr.shape}"
                )

            if pred_arr.shape[1] != n_expected_segments:
                raise ValueError(
                    f"Wrong number of segments for transcript {transcript_id}: "
                    f"got {pred_arr.shape[1]}, expected {n_expected_segments}"
                )

            category = self._get_stratifier_value_from_mapping(meta, stratifier)
            detail = {
                "transcript_id": transcript_id,
                "gene_id": gene_id,
                "transcript_type": transcript_type,
                "strand": meta["strand"],
                "seqid": meta["seqid"],
                "coord": meta["coord"],
                "length": int(pred_arr.shape[0]),
                "category": category,
                "segments": {},
            }

            for seg_idx, segment in enumerate(segments):
                pred_col = pred_arr[:, seg_idx]
                target_col = target_arr[:, seg_idx]

                self._validate_binary_vector(
                    pred_col,
                    name=f"preds[{idx}][:, {seg_idx}] for transcript {transcript_id}"
                )
                self._validate_binary_vector(
                    target_col,
                    name=f"targets[{idx}][:, {seg_idx}] for transcript {transcript_id}"
                )

                pred_set = set(self._find_segments_ones(pred_col))
                target_set = set(self._find_segments_ones(target_col))

                match: bool | None
                if len(target_set) == 0:
                    match = None
                else:
                    if transcript_type != "mRNA" and segment == "CDS":
                        raise ValueError("CDS in the non-protein-coding gene")
                    match = pred_set == target_set
                    if match:
                        if self._normalize_stratifier_name(stratifier) == "transcript_id":
                            result_sets[category][seg_idx].add(transcript_id)
                        else:
                            result_sets[category][seg_idx].add(gene_id)

                detail["segments"][segment] = {
                    "predicted": _segments_to_lists(pred_set),
                    "target": _segments_to_lists(target_set),
                    "match": match,
                }

            details.append(detail)

        raw_result = {
            category: [len(seg_set) for seg_set in per_segment_sets]
            for category, per_segment_sets in result_sets.items()
        }
        return self._pack_output(
            mode="python",
            raw_result=raw_result,
            stratifier=stratifier,
            types=list(types),
            segments=list(segments),
            details=details,
        )

    def _parse_mapping_record(self, record: str) -> Dict[str, str]:
        parts = str(record).split("|")
        if len(parts) != 7:
            raise ValueError(
                "Each mapping entry must have format "
                "'transcript_id|gene_id|transcript_type|strand|genome|chrom|coord'"
            )

        transcript_id, gene_id, transcript_type, strand, genome, chrom, coord = parts

        return {
            "transcript_id": transcript_id,
            "gene_id": gene_id,
            "transcript_type": transcript_type,
            "strand": strand,
            "genome": genome,
            "chromosome": chrom,
            "seqid": chrom,
            "coord": coord,
        }

    def _initialize_result_sets_from_mapping(
        self,
        meta_df: pd.DataFrame,
        stratifier: str,
        segments: Sequence[str],
    ) -> Dict[Any, list[set[str]]]:
        keys = self._collect_all_stratifier_keys_from_mapping(meta_df=meta_df, stratifier=stratifier)
        return {key: [set() for _ in segments] for key in keys}

    def _collect_all_stratifier_keys_from_mapping(
        self,
        meta_df: pd.DataFrame,
        stratifier: str,
    ) -> list[Any]:
        stratifier = self._normalize_stratifier_name(stratifier)

        if stratifier == "gene_id":
            keys = meta_df["gene_id"].dropna().unique().tolist()
        elif stratifier == "transcript_id":
            keys = meta_df["transcript_id"].dropna().unique().tolist()
        elif stratifier == "transcript_type":
            keys = meta_df["transcript_type"].dropna().unique().tolist()
        elif stratifier == "seqid":
            keys = meta_df["seqid"].dropna().unique().tolist()
        elif stratifier == "strand":
            keys = meta_df["strand"].dropna().unique().tolist()
        else:
            raise KeyError(f"Unsupported stratifier: {stratifier!r}")

        return sorted(keys)

    def _get_stratifier_value_from_mapping(
        self,
        meta: Dict[str, str],
        stratifier: str,
    ) -> Any:
        stratifier = self._normalize_stratifier_name(stratifier)

        if stratifier == "gene_id":
            value = meta["gene_id"]
        elif stratifier == "transcript_id":
            value = meta["transcript_id"]
        elif stratifier == "transcript_type":
            value = self._normalize_transcript_type(meta["transcript_type"])
        elif stratifier == "seqid":
            value = meta["seqid"]
        elif stratifier == "strand":
            value = meta["strand"]
        else:
            raise KeyError(f"Unsupported stratifier: {stratifier!r}")

        if pd.isna(value):
            return "<NA>"
        return value

    def _find_segments_ones(self, array: np.ndarray) -> list[tuple[int, int]]:
        ones_idx = np.where(array == 1)[0]
        if ones_idx.size == 0:
            return []

        split_idx = np.where(np.diff(ones_idx) > 1)[0] + 1
        split_ones_idx = np.split(ones_idx, split_idx)

        return [(int(segment[0]), int(segment[-1]) + 1) for segment in split_ones_idx]

    def _validate_binary_vector(self, array: np.ndarray, name: str) -> None:
        arr = np.asarray(array)
        if arr.ndim != 1:
            raise ValueError(f"{name} must be a 1D vector")

        unique_values = np.unique(arr)
        if not np.isin(unique_values, [0, 1]).all():
            raise ValueError(
                f"{name} must contain only 0/1 values, got {unique_values.tolist()}"
            )

    def _pack_output(
        self,
        mode: str,
        raw_result: Dict[Any, list[int]],
        stratifier: str,
        types: list[str],
        segments: list[str],
        details: list[dict[str, Any]],
    ) -> Dict[str, Any]:
        rows = []
        for category, counts in raw_result.items():
            values = {segment: int(counts[idx]) for idx, segment in enumerate(segments)}
            rows.append(
                {
                    "category": str(category),
                    "values": values,
                    "total": int(sum(values.values())),
                }
            )

        totals_by_segment = {
            segment: int(sum(raw_result[category][idx] for category in raw_result))
            for idx, segment in enumerate(segments)
        }

        return {
            "mode": mode,
            "stratifier": stratifier,
            "types": types,
            "segments": segments,
            "raw_result": {str(key): [int(x) for x in value] for key, value in raw_result.items()},
            "rows": rows,
            "totals_by_segment": totals_by_segment,
            "details": details,
            "n_categories": len(rows),
            "n_transcripts": len(details),
        }


def compute_python_metric(
    preds: Sequence[Sequence[Sequence[int]]],
    targets: Sequence[Sequence[Sequence[int]]],
    mapping: Sequence[str],
    stratifier: str,
    types: Sequence[str] = DEFAULT_TYPES,
    segments: Sequence[str] = DEFAULT_SEGMENTS,
) -> dict[str, Any]:
    evaluator = GeneLevelEvaluator()
    return evaluator.gene_level_python_detailed(
        preds=preds,
        targets=targets,
        mapping=mapping,
        stratifier=stratifier,
        types=types,
        segments=segments,
    )


def compute_gff_metric(
    pred_gff: Union[PathLike, pd.DataFrame, str],
    true_gff: Union[PathLike, pd.DataFrame, str],
    stratifier: str,
    types: Sequence[str] = DEFAULT_TYPES,
    segments: Sequence[str] = DEFAULT_SEGMENTS,
) -> dict[str, Any]:
    evaluator = GeneLevelEvaluator()
    return evaluator.gene_level_gff_detailed(
        pred_gff=pred_gff,
        true_gff=true_gff,
        stratifier=stratifier,
        types=types,
        segments=segments,
    )
