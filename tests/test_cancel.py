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
