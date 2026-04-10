"""Tests for pure logic methods in squidlib.app.SquidApp.

These tests instantiate SquidApp but don't mount or run it,
so they test internal logic without needing Textual's async harness.
"""

from unittest.mock import patch, MagicMock

from squidlib.constants import ALL_JOBS, PARTITIONS, UNASSIGNED, SlurmJob


def make_app():
    """Create a SquidApp instance without mounting it."""
    with patch("squidlib.app.load_config", return_value={"lists": {}, "assignments": {}, "notes": {}}):
        from squidlib.app import SquidApp
        app = SquidApp(refresh_interval=180)
    return app


class TestAllListNames:
    def test_default_lists(self):
        app = make_app()
        names = app._all_list_names()
        assert names[0] == ALL_JOBS
        assert names[1] == UNASSIGNED
        assert len(names) == 2

    def test_with_custom_lists(self):
        app = make_app()
        app.custom_lists = {"Beta": [], "Alpha": []}
        names = app._all_list_names()
        assert names == [ALL_JOBS, UNASSIGNED, "Alpha", "Beta"]


class TestAssignedJobIds:
    def test_empty(self):
        app = make_app()
        assert app._assigned_job_ids() == set()

    def test_collects_from_all_lists(self):
        app = make_app()
        app.custom_lists = {"A": ["1", "2"], "B": ["2", "3"]}
        assert app._assigned_job_ids() == {"1", "2", "3"}


class TestIsActive:
    def test_running_is_active(self):
        app = make_app()
        assert app._is_active(SlurmJob(state="RUNNING")) is True

    def test_pending_is_active(self):
        app = make_app()
        assert app._is_active(SlurmJob(state="PENDING")) is True

    def test_completed_is_not_active(self):
        app = make_app()
        assert app._is_active(SlurmJob(state="COMPLETED")) is False

    def test_failed_is_not_active(self):
        app = make_app()
        assert app._is_active(SlurmJob(state="FAILED")) is False


class TestCountJobsInList:
    def test_all_jobs_counts_active(self):
        app = make_app()
        app.jobs = [
            SlurmJob(job_id="1", state="RUNNING"),
            SlurmJob(job_id="2", state="COMPLETED"),
            SlurmJob(job_id="3", state="PENDING"),
        ]
        assert app._count_jobs_in_list(ALL_JOBS) == 2

    def test_unassigned_excludes_assigned(self):
        app = make_app()
        app.jobs = [
            SlurmJob(job_id="1", state="RUNNING"),
            SlurmJob(job_id="2", state="RUNNING"),
        ]
        app.custom_lists = {"mylist": ["1"]}
        assert app._count_jobs_in_list(UNASSIGNED) == 1

    def test_custom_list_counts_members(self):
        app = make_app()
        app.jobs = [
            SlurmJob(job_id="1", state="RUNNING"),
            SlurmJob(job_id="2", state="COMPLETED"),
            SlurmJob(job_id="3", state="RUNNING"),
        ]
        app.custom_lists = {"mylist": ["1", "2"]}
        assert app._count_jobs_in_list("mylist") == 2


class TestGetEffectiveIds:
    def test_returns_selected_if_any(self):
        app = make_app()
        app.selected_ids = {"1", "2"}
        assert set(app._get_effective_ids()) == {"1", "2"}

    def test_returns_cursor_job_when_nothing_selected(self):
        app = make_app()
        app.selected_ids = set()
        # Mock _get_cursor_job_id since it requires mounted widgets
        app._get_cursor_job_id = MagicMock(return_value="99")
        assert app._get_effective_ids() == ["99"]

    def test_returns_empty_when_no_cursor(self):
        app = make_app()
        app.selected_ids = set()
        app._get_cursor_job_id = MagicMock(return_value=None)
        assert app._get_effective_ids() == []


class TestOnNewList:
    def test_rejects_reserved_names(self):
        app = make_app()
        for name in [ALL_JOBS, UNASSIGNED, PARTITIONS, None, ""]:
            app._on_new_list(name)
        assert app.custom_lists == {}

    def test_adds_new_list(self):
        app = make_app()
        app._save = MagicMock()
        app._rebuild_sidebar = MagicMock()
        app._select_sidebar_item = MagicMock()
        # Mock watch_active_list to avoid query_one on unmounted app
        app.watch_active_list = MagicMock()
        app._on_new_list("My List")
        assert "My List" in app.custom_lists

    def test_does_not_duplicate(self):
        app = make_app()
        app.custom_lists = {"Existing": ["1"]}
        app._save = MagicMock()
        app._on_new_list("Existing")
        assert app.custom_lists == {"Existing": ["1"]}


class TestOnMove:
    def test_moves_job_to_target(self):
        app = make_app()
        app.custom_lists = {"A": ["1"], "B": []}
        app._save = MagicMock()
        app._populate_table = MagicMock()
        app._rebuild_sidebar = MagicMock()
        app._on_move(["1"], "B")
        assert "1" not in app.custom_lists["A"]
        assert "1" in app.custom_lists["B"]

    def test_move_to_all_jobs_removes_from_lists(self):
        app = make_app()
        app.custom_lists = {"A": ["1"]}
        app._save = MagicMock()
        app._populate_table = MagicMock()
        app._rebuild_sidebar = MagicMock()
        app._on_move(["1"], ALL_JOBS)
        assert "1" not in app.custom_lists["A"]


class TestOnNote:
    def test_saves_note(self):
        app = make_app()
        app.jobs = [SlurmJob(job_id="1")]
        app._save = MagicMock()
        app._populate_table = MagicMock()
        app._on_note("1", "important job")
        assert app.notes["1"] == "important job"

    def test_clears_note(self):
        app = make_app()
        app.notes = {"1": "old note"}
        app.jobs = [SlurmJob(job_id="1")]
        app._save = MagicMock()
        app._populate_table = MagicMock()
        app._on_note("1", "")
        assert "1" not in app.notes

    def test_none_value_does_nothing(self):
        app = make_app()
        app.notes = {"1": "keep this"}
        app._save = MagicMock()
        app._on_note("1", None)
        assert app.notes["1"] == "keep this"
        app._save.assert_not_called()


class TestOnCancelResult:
    def test_does_nothing_when_not_confirmed(self):
        app = make_app()
        app._do_cancel = MagicMock()
        app._on_cancel_result(False, ["1"])
        app._do_cancel.assert_not_called()

    def test_does_nothing_when_no_ids(self):
        app = make_app()
        app._do_cancel = MagicMock()
        app._on_cancel_result(True, None)
        app._do_cancel.assert_not_called()

    def test_cancels_when_confirmed(self):
        app = make_app()
        app._do_cancel = MagicMock()
        app.selected_ids = {"1", "2"}
        app._on_cancel_result(True, ["1", "2"])
        assert app._do_cancel.call_count == 2
        assert app.selected_ids == set()
