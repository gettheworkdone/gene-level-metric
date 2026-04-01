from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, Sequence, Union

import pandas as pd
from Bio import SeqIO
from Bio.Seq import Seq

PathLike = Union[str, Path]


class BUSCOEvaluator:
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

    def busco_prepare_gff(
        self,
        pred_gff: Union[PathLike, pd.DataFrame],
        true_gff: Union[PathLike, pd.DataFrame],
        fasta_path: PathLike,
        protein_fasta: PathLike,
        lineage: PathLike,
        out_dir: PathLike,
        out_name: str = "busco_run",
        cpu: int = 2,
        busco_exe: str = "busco",
    ) -> Dict[str, int]:
        true_df = self._read_gff(true_gff, mode="true")
        pred_df = self._read_gff(pred_gff, mode="pred")

        types = ["mRNA"]
        segment = "CDS"

        transcript_meta = self._build_transcript_meta(true_df, types=types)
        true_transcript_ids = transcript_meta.index.tolist()
        pred_transcript_ids = set(pred_df["ID"].tolist()) & set(true_transcript_ids)

        true_df_segments = true_df[true_df["type"].isin([segment])].copy()
        pred_df_segments = pred_df[pred_df["type"].isin([segment])].copy()

        fasta_path = Path(fasta_path)
        records = SeqIO.to_dict(SeqIO.parse(str(fasta_path), "fasta"))

        proteins = []
        for transcript_id in pred_transcript_ids:
            meta = transcript_meta.loc[transcript_id]
            transcript_start = int(meta["start"])
            transcript_end = int(meta["end"])
            transcript_strand = meta["strand"]
            transcript_chrom = meta["seqid"]

            transcript_true_df_segments = true_df_segments[true_df_segments["Parent"] == transcript_id].copy()
            if transcript_true_df_segments.empty:
                continue

            transcript_pred_df_segments = pred_df_segments[pred_df_segments["ID"] == transcript_id].copy()
            pred_segments_set = self.search_segments(
                transcript_df_segments=transcript_pred_df_segments,
                segment=segment,
                transcript_start=0,
            )
            if not pred_segments_set:
                continue

            transcript_seq = self.get_nt_sequence(records, transcript_chrom, transcript_start, transcript_end)
            cds_seq = self.get_cds_sequence(transcript_seq, pred_segments_set)
            protein = self._translate_protein(cds_seq, transcript_strand)
            if protein:
                proteins.append((transcript_id, protein))

        protein_fasta = Path(protein_fasta)
        protein_fasta.parent.mkdir(parents=True, exist_ok=True)
        with protein_fasta.open("w") as handle:
            for transcript_id, protein in proteins:
                handle.write(f">{transcript_id}\n{protein}\n")

        busco_json = self.run_busco(
            protein_fasta=protein_fasta,
            lineage=lineage,
            out_dir=out_dir,
            out_name=out_name,
            cpu=cpu,
            busco_exe=busco_exe,
        )

        return self.parse_busco_json(busco_json)

    def _read_gff(self, gff: Union[PathLike, pd.DataFrame], mode: str) -> pd.DataFrame:
        if isinstance(gff, pd.DataFrame):
            df = gff.copy()
        else:
            df = pd.read_csv(
                gff,
                sep="\t",
                names=self.GFF_COLUMNS,
                header=None,
                comment="#",
                dtype=str,
            )

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

    def _build_transcript_meta(self, true_df: pd.DataFrame, types: Sequence[str]) -> pd.DataFrame:
        gene_ids = true_df.loc[true_df["type"] == "gene", "ID"].dropna().unique().tolist()
        transcript_rows = true_df[true_df["Parent"].isin(gene_ids) & true_df["type"].isin(types)].copy()
        records = []
        for _, row in transcript_rows.iterrows():
            rec = row.to_dict()
            rec["transcript_id"] = str(row["ID"])
            rec["gene_id"] = str(row["Parent"])
            rec["transcript_type"] = str(row["type"]).strip()
            records.append(rec)
        out = pd.DataFrame(records)
        out = out.drop_duplicates(subset=["transcript_id"]).set_index("transcript_id", drop=False)
        return out

    @staticmethod
    def _translate_protein(seq: str, strand: str):
        protein_vars_3_frames = []
        source = seq if strand == "+" else str(Seq(seq).reverse_complement())
        for orf in range(3):
            trimmed = source[orf:]
            trimmed = trimmed[: len(trimmed) - (len(trimmed) % 3)]
            if not trimmed:
                continue
            protein_var = str(Seq(trimmed).translate(to_stop=False))
            protein_vars_3_frames.extend([p for p in protein_var.split("*") if p])
        return max(protein_vars_3_frames, key=len, default="")

    @staticmethod
    def get_nt_sequence(records, chrom_id: str, start: int, end: int) -> str:
        chrom_seq = records[chrom_id].seq
        return str(chrom_seq[start:end]).upper()

    @staticmethod
    def get_cds_sequence(transcript_seq: str, segments: Sequence[tuple[int, int]]) -> str:
        parts = [transcript_seq[start:end] for start, end in sorted(list(segments), key=lambda x: (x[0], x[1]))]
        return "".join(parts).upper()

    @staticmethod
    def search_segments(
        transcript_df_segments: pd.DataFrame,
        segment: Union[str, Sequence[str]] = "CDS",
        transcript_start: int = 0,
    ) -> list[tuple[int, int]]:
        if isinstance(segment, str):
            segment = [segment]
        df = transcript_df_segments[transcript_df_segments["type"].isin(segment)].copy()
        if df.empty:
            return []
        df["start"] = df["start"].astype(int) - int(transcript_start)
        df["end"] = df["end"].astype(int) - int(transcript_start)
        df = df.sort_values(["start", "end"]).reset_index(drop=True)
        return [(int(row["start"]), int(row["end"])) for _, row in df.iterrows()]

    @staticmethod
    def run_busco(
        protein_fasta: PathLike,
        lineage: PathLike,
        out_dir: PathLike,
        out_name: str,
        cpu: int = 2,
        busco_exe: str = "busco",
    ) -> Path:
        protein_fasta = Path(protein_fasta).resolve()
        lineage = Path(lineage).resolve()
        out_dir = Path(out_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            busco_exe,
            "-i", str(protein_fasta),
            "-l", str(lineage),
            "--offline",
            "-m", "proteins",
            "-o", out_name,
            "-c", str(cpu),
        ]
        env = os.environ.copy()
        env["PYTHONWARNINGS"] = "ignore::SyntaxWarning"
        subprocess.run(cmd, cwd=str(out_dir), env=env, check=True, capture_output=True, text=True)
        return BUSCOEvaluator._find_busco_summary_json(out_dir / out_name)

    @staticmethod
    def _find_busco_summary_json(busco_run_dir: PathLike) -> Path:
        for json_path in sorted(Path(busco_run_dir).rglob("*.json")):
            try:
                with open(json_path, "r") as handle:
                    data = json.load(handle)
            except Exception:
                continue
            if isinstance(data, dict) and isinstance(data.get("results"), dict):
                if "Complete BUSCOs" in data["results"] and "Fragmented BUSCOs" in data["results"]:
                    return json_path
        raise FileNotFoundError("Could not find BUSCO summary JSON.")

    @staticmethod
    def parse_busco_json(busco_json: PathLike) -> Dict[str, int]:
        with Path(busco_json).open("r") as handle:
            data = json.load(handle)
        results = data.get("results", {})
        complete = int(results["Complete BUSCOs"])
        fragmented = int(results["Fragmented BUSCOs"])
        return {
            "Complete": complete,
            "Fragmented": fragmented,
            "Missing": max(275 - complete - fragmented, 0),
        }
