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


def test_view_dashboard_route_and_password_guard_exist():
    source = SOURCE.read_text(encoding="utf-8")

    assert "VIEW_PWD = os.getenv(\"VIEW_PWD\", \"xryu\")" in source
    assert '@app.get("/view", response_class=HTMLResponse)' in source
    assert "def viewDashboard" in source
    assert "if pwd != VIEW_PWD:" in source


def test_operation_log_contains_ip_location_fields():
    source = SOURCE.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS operation_log" in source
    assert "ip_country" in source
    assert "ip_region" in source
    assert "ip_city" in source
    assert "def getClientLocation" in source


def test_view_dashboard_has_period_filter_options():
    source = SOURCE.read_text(encoding="utf-8")

    assert 'VIEW_PERIODS = {' in source
    assert '"24h"' in source
    assert '"7d"' in source
    assert '"30d"' in source
    assert '"all"' in source
    assert 'def viewDashboard(request: Request, pwd: str = "", period: str = "7d")' in source


def test_view_dashboard_has_ip_location_top_aggregation():
    source = SOURCE.read_text(encoding="utf-8")

    assert "属地来源 Top" in source
    assert "GROUP BY ip_country, ip_region, ip_city" in source
    assert "ORDER BY cnt DESC" in source
