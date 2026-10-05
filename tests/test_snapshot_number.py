from wadi_scraper.store import RunSummary


def test_run_summary_has_snapshot_number():
    r = RunSummary(
        id=37,
        competitor_id="reebok",
        status="ok",
        started_at=None,
        finished_at=None,
        pages_count=1,
        blogs_count=0,
        collections_count=0,
        other_count=0,
        has_report=True,
        snapshot_number=8,
    )
    assert r.id == 37
    assert r.snapshot_number == 8
