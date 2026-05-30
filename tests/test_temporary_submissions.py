import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import time
from backend.leaderboard_service import LeaderboardService


def wait_status(service, sid, timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        st = service.submission_status(sid)
        if st.get("status") in {"completed", "failed", "expired"}:
            return st
        time.sleep(0.05)
    raise TimeoutError(sid)


def setup_service(tmp_path, monkeypatch, fail_first=False):
    req = tmp_path / "leaderboard_required_files"
    (req / "lineage" / "mammalia_odb10").mkdir(parents=True)
    (req / "chr20.gff").write_text("x")
    (req / "Hs_NC_060944.1.fa").write_text("x")
    calls = {"n": 0}

    def fake_metric(**kwargs):
        calls["n"] += 1
        if fail_first and calls["n"] == 1:
            raise RuntimeError("boom")
        return {"raw_result": {"lnc_RNA": [1, 0], "mRNA": [2, 3]}}

    class FakeBusco:
        def busco_prepare_gff(self, **kwargs):
            Path(kwargs["output_gff_path"]).write_text("colored")
            return {"Complete": 7, "Fragmented": 2, "Missing": 1}

    monkeypatch.setattr("backend.leaderboard_service.compute_gff_metric", fake_metric)
    monkeypatch.setattr("backend.leaderboard_service.BUSCOEvaluator", FakeBusco)
    return LeaderboardService(tmp_path)


def test_temporary_submission_not_in_status(tmp_path, monkeypatch):
    s = setup_service(tmp_path, monkeypatch)
    sid = s.enqueue_submission("m1", "gff")["submission_id"]
    st = wait_status(s, sid)
    assert st["status"] == "completed"
    overall = s.status()
    assert all(
        not str(r.get("model_id", "")).startswith("temporary::")
        for r in overall["gene_rows"]
    )
    assert all(
        not str(r.get("model_id", "")).startswith("temporary::")
        for r in overall["busco_rows"]
    )
    assert overall.get("user_gene_rows", []) == []
    assert overall.get("user_busco_rows", []) == []


def test_no_durable_temp_files(tmp_path, monkeypatch):
    s = setup_service(tmp_path, monkeypatch)
    sid = s.enqueue_submission("m2", "gff")["submission_id"]
    wait_status(s, sid)
    assert not (tmp_path / "leaderboard_uploads").exists()
    assert not (tmp_path / "leaderboard_runs" / f"user_{sid}").exists()


def test_result_payload_contains_rows(tmp_path, monkeypatch):
    s = setup_service(tmp_path, monkeypatch)
    sid = s.enqueue_submission("m3", "gff")["submission_id"]
    st = wait_status(s, sid)
    assert st["model_id"].startswith("temporary::")
    assert "gene_row" in st and "busco_row" in st
    assert st["busco_row"].get("colored_gff_text") == "colored"


def test_failed_job_does_not_kill_queue(tmp_path, monkeypatch):
    s = setup_service(tmp_path, monkeypatch, fail_first=True)
    sid1 = s.enqueue_submission("bad", "gff")["submission_id"]
    sid2 = s.enqueue_submission("good", "gff")["submission_id"]
    st1 = wait_status(s, sid1)
    st2 = wait_status(s, sid2)
    assert st1["status"] == "failed"
    assert st2["status"] == "completed"
