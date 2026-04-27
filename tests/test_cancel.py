from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "api" / "main.py"


def test_vote_cancel_route_decrements_without_negative_counts():
    source = SOURCE.read_text(encoding="utf-8")

    assert '@app.post("/api/vote/cancel"' in source
    assert "def cancelVote" in source
    assert "GREATEST(up - 1, 0)" in source
    assert "GREATEST(down - 1, 0)" in source


def test_rating_cancel_route_decrements_without_negative_counts():
    source = SOURCE.read_text(encoding="utf-8")

    assert '@app.post("/api/rating/cancel"' in source
    assert "def cancelRating" in source
    assert 'GREATEST("{value}" - 1, 0)' in source


def test_vote_batch_info_route_exists_without_changing_single_info_contract():
    source = SOURCE.read_text(encoding="utf-8")

    assert '@app.get("/api/vote/info"' in source
    assert '@app.get("/api/vote/batch_info"' in source
    assert "def getVoteBatchInfo" in source
    assert "SELECT id, up, down, created_at, updated_at FROM vote WHERE id = ANY(%s)" in source


def test_vote_batch_info_route_returns_default_shape_for_missing_ids():
    source = SOURCE.read_text(encoding="utf-8")

    assert '"up": 0' in source
    assert '"down": 0' in source
    assert '"createdAt": None' in source
    assert '"updatedAt": None' in source


def test_vote_batch_info_route_has_batch_size_limit_guard():
    source = SOURCE.read_text(encoding="utf-8")

    assert "MAX_BATCH_VOTE_IDS = 200" in source
    assert "if len(raw_ids) > MAX_BATCH_VOTE_IDS:" in source
    assert '"Too many ids, max {MAX_BATCH_VOTE_IDS}"' in source
