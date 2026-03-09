from __future__ import annotations

import warnings
from typing import Any, Iterable, Sequence

import numpy as np
from Bio import Seq

DEFAULT_DSS = ["GT", "GC", "AT"]
DEFAULT_ASS = ["AG", "AC", "TG"]

SIMPLE_EXAMPLE = {
    "preds": [
        [0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0],
        [0, 1, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0],
    ],
    "targets": [
        [0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0],
        [0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0],
    ],
    "mapping": [
        "chr1|mRNA|GENE0001|TX0001|+|1-12",
        "chr1|lncRNA|GENE0002|TX0002|+|1-12",
    ],
    "dna_sequences": [
        "ATGCGTAACTGA",
        "TTACTGACCTGA",
    ],
    "cds_heuristics": False,
    "splice_filter": False,
    "dss": DEFAULT_DSS,
    "ass": DEFAULT_ASS,
}

HEURISTIC_EXAMPLE = {
    "preds": [
        [1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1],
    ],
    "targets": [
        [0, 0, 0, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1],
    ],
    "mapping": [
        "chr1|mRNA|GENE0003|TX0003|+|1-22",
    ],
    "dna_sequences": [
        "AAAATGAGAAACCCGTGGGTAA",
    ],
    "cds_heuristics": True,
    "splice_filter": True,
    "dss": DEFAULT_DSS,
    "ass": DEFAULT_ASS,
}

EXAMPLE_PAYLOADS = {
    "simple": SIMPLE_EXAMPLE,
    "heuristic": HEURISTIC_EXAMPLE,
}


def find_segments_ones(array: np.ndarray) -> list[tuple[int, int]]:
    ones_idx = np.where(array == 1)[0]
    if ones_idx.size == 0:
        return []

    split_idx = np.where(np.diff(ones_idx) > 1)[0] + 1
    split_ones_idx = np.split(ones_idx, split_idx)
    return [(int(segment[0]), int(segment[-1]) + 1) for segment in split_ones_idx]



def get_reverse_complements(seqs: Sequence[str]) -> list[str]:
    return [str(Seq.reverse_complement(seq)) for seq in seqs]



def check_splice(
    seq: str,
    exons: Iterable[tuple[int, int]],
    left_edge: Sequence[str],
    right_edge: Sequence[str],
) -> set[tuple[int, int]]:
    noshort_exons = [(start, end) for start, end in exons if end - start >= 3]
    sorted_exons = sorted(noshort_exons, key=lambda x: x[0])
    n = len(sorted_exons)
    if n < 3:
        return set(sorted_exons)

    correct = {sorted_exons[0], sorted_exons[-1]}
    seq_len = len(seq)

    for i in range(1, n - 1):
        start, end = sorted_exons[i]
        if start >= 2 and seq[start - 2 : start] in left_edge:
            if end + 2 <= seq_len and seq[end : end + 2] in right_edge:
                correct.add((start, end))

    return correct



def exon2cds(exon_preds: np.ndarray, seq: str, strand: str = "+") -> np.ndarray:
    if len(seq) < 3 or np.sum(exon_preds) < 3:
        return np.zeros_like(exon_preds)

    seq = seq.upper()
    if strand == "-":
        seq = str(Seq.reverse_complement(seq))
        exon_preds = exon_preds[::-1]

    exon_positions = np.where(exon_preds == 1)[0]
    exon_seq = "".join(np.array(list(seq))[exon_positions])

    best_len_aa = 0
    best_nt_start: int | None = None
    best_nt_end: int | None = None

    for frame in range(3):
        sub_seq = exon_seq[frame:]
        if len(sub_seq) < 3:
            continue

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            aa_seq = str(Seq.translate(sub_seq, to_stop=False))

        protein_split = aa_seq.split("*")
        aa_seqs = [
            protein + "*" if i < len(protein_split) - 1 else protein
            for i, protein in enumerate(protein_split)
        ]

        aa_start = 0
        for protein in aa_seqs:
            prot_len = len(protein)
            if prot_len == 0:
                continue

            nt_start = frame + aa_start * 3
            nt_end = nt_start + prot_len * 3
            aa_start += prot_len

            if "M" in protein and "*" in protein:
                m_pos = protein.find("M")
                orf = protein[m_pos:]
                orf_len_aa = len(orf)

                if orf_len_aa > best_len_aa:
                    best_len_aa = orf_len_aa
                    best_nt_start = nt_start + m_pos * 3
                    best_nt_end = nt_end

    if best_nt_start is None or best_nt_end is None:
        return np.zeros_like(exon_preds)

    cds_mask = np.zeros_like(exon_preds)
    cds_positions = exon_positions[best_nt_start:best_nt_end]
    cds_mask[cds_positions] = 1

    if strand == "-":
        cds_mask = cds_mask[::-1]

    return cds_mask



def parse_mapping_entry(raw_mapping: str) -> dict[str, str]:
    parts = raw_mapping.split("|")
    if len(parts) != 6:
        raise ValueError(
            "Each mapping row must have 6 fields: "
            "chrom|gene_type|gene_id|transcript_id|strand|coord"
        )

    chrom, gene_type, gene_id, transcript_id, strand, coord = parts
    if strand not in {"+", "-"}:
        raise ValueError(f"Invalid strand '{strand}' in mapping entry: {raw_mapping}")

    return {
        "chrom": chrom,
        "gene_type": gene_type,
        "gene_id": gene_id,
        "transcript_id": transcript_id,
        "strand": strand,
        "coord": coord,
        "raw": raw_mapping,
    }



def normalize_dna_sequences(dna_sequences: Any, n_items: int) -> list[str]:
    if dna_sequences in (None, ""):
        return [""] * n_items

    if isinstance(dna_sequences, str):
        cleaned = "".join(dna_sequences.split()).upper()
        return [cleaned] * n_items

    if isinstance(dna_sequences, Sequence):
        cleaned = ["".join(str(item).split()).upper() for item in dna_sequences]
        if len(cleaned) == 1 and n_items > 1:
            return cleaned * n_items
        if len(cleaned) != n_items:
            raise ValueError(
                "DNA sequences must be empty, a single sequence, or a list with the same length as preds/targets."
            )
        return cleaned

    raise ValueError("Unsupported DNA sequence format.")



def validate_binary_row(row: Sequence[Any], label: str, row_index: int) -> np.ndarray:
    arr = np.asarray(row, dtype=int)
    if arr.ndim != 1:
        raise ValueError(f"{label}[{row_index}] must be a flat list of 0/1 values.")

    bad_values = arr[(arr != 0) & (arr != 1)]
    if bad_values.size > 0:
        raise ValueError(
            f"{label}[{row_index}] must contain only 0 or 1. Found: {sorted(set(bad_values.tolist()))}"
        )

    return arr



def gene_level_metric(
    preds: Sequence[Sequence[int]],
    targets: Sequence[Sequence[int]],
    mapping: Sequence[str],
    dna_sequences: Any = "",
    cds_heuristics: bool = False,
    splice_filter: bool = False,
    dss: Sequence[str] | None = None,
    ass: Sequence[str] | None = None,
) -> dict[str, Any]:
    if len(preds) != len(targets):
        raise ValueError("Predictions and targets must contain the same number of transcripts.")
    if len(mapping) != len(preds):
        raise ValueError("Mapping length must match the number of prediction/target rows.")
    if len(preds) == 0:
        raise ValueError("At least one transcript is required.")

    donor_sites = [motif.upper() for motif in (dss or DEFAULT_DSS)]
    acceptor_sites = [motif.upper() for motif in (ass or DEFAULT_ASS)]
    dna_list = normalize_dna_sequences(dna_sequences, len(preds))

    matched = 0
    details: list[dict[str, Any]] = []

    for i, (pred_row, target_row, raw_mapping, dna_seq) in enumerate(
        zip(preds, targets, mapping, dna_list)
    ):
        pred_arr = validate_binary_row(pred_row, "preds", i)
        target_arr = validate_binary_row(target_row, "targets", i)

        if len(pred_arr) != len(target_arr):
            raise ValueError(
                f"preds[{i}] and targets[{i}] must have the same length. "
                f"Got {len(pred_arr)} and {len(target_arr)}."
            )

        if dna_seq and len(dna_seq) != len(pred_arr):
            raise ValueError(
                f"DNA sequence length for item {i} must match mask length. "
                f"Got {len(dna_seq)} and {len(pred_arr)}."
            )

        mapping_info = parse_mapping_entry(raw_mapping)
        strand = mapping_info["strand"]

        raw_pred_segments = set(find_segments_ones(pred_arr))
        pred_segments = set(raw_pred_segments)
        target_segments = set(find_segments_ones(target_arr))

        if splice_filter:
            if dna_seq == "":
                raise ValueError("DNA sequence is required when splice_filter=True.")

            if strand == "+":
                pred_segments = check_splice(dna_seq, pred_segments, acceptor_sites, donor_sites)
            else:
                pred_segments = check_splice(
                    dna_seq,
                    pred_segments,
                    get_reverse_complements(donor_sites),
                    get_reverse_complements(acceptor_sites),
                )

        if cds_heuristics:
            if dna_seq == "":
                raise ValueError("DNA sequence is required when cds_heuristics=True.")

            cds_preds = np.zeros_like(pred_arr, dtype=int)
            for start, end in pred_segments:
                cds_preds[start:end] = 1
            pred_segments = set(find_segments_ones(exon2cds(cds_preds, dna_seq, strand=strand)))

        is_match = pred_segments == target_segments
        if is_match:
            matched += 1

        details.append(
            {
                **mapping_info,
                "index": i,
                "length": int(len(pred_arr)),
                "raw_pred_segments": sorted(raw_pred_segments),
                "final_pred_segments": sorted(pred_segments),
                "target_segments": sorted(target_segments),
                "match": is_match,
            }
        )

    total = len(preds)
    score = matched / total
    return {
        "score": score,
        "matched_genes": matched,
        "total_genes": total,
        "details": details,
        "parameters": {
            "cds_heuristics": cds_heuristics,
            "splice_filter": splice_filter,
            "dss": donor_sites,
            "ass": acceptor_sites,
        },
    }
