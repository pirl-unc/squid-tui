"""Tests for squidlib.constants."""

from rich.text import Text

from squidlib.constants import (
    QUEUE_STATES,
    RUNNING_STATES,
    SQUEUE_FIELDS,
    SQUEUE_FORMAT,
    STATE_STYLES,
    SlurmJob,
)


class TestSlurmJob:
    def test_default_init(self):
        job = SlurmJob()
        assert job.job_id == ""
        assert job.state == ""
        assert job.note == ""

    def test_init_with_fields(self):
        job = SlurmJob(job_id="12345", state="RUNNING", name="myjob", user="alice")
        assert job.job_id == "12345"
        assert job.state == "RUNNING"
        assert job.name == "myjob"
        assert job.user == "alice"

    def test_row_length(self):
        job = SlurmJob(job_id="1", partition="gpu", name="test", state="RUNNING")
        row = job.row()
        assert len(row) == 10

    def test_row_field_order(self):
        job = SlurmJob(
            job_id="1", partition="gpu", name="test", state="PENDING",
            time="1:00", time_limit="2:00", cpus="4", memory="8G",
            nodelist="node01", note="my note",
        )
        row = job.row()
        assert row[0] == "1"
        assert row[1] == "gpu"
        assert row[2] == "test"
        # row[3] is styled state
        assert row[4] == "1:00"
        assert row[5] == "2:00"
        assert row[6] == "4"
        assert row[7] == "8G"
        assert row[8] == "node01"
        assert row[9] == "my note"

    def test_row_known_state_returns_rich_text(self):
        for state in ("RUNNING", "PENDING", "FAILED", "CANCELLED", "COMPLETED"):
            job = SlurmJob(state=state)
            row = job.row()
            assert isinstance(row[3], Text), f"Expected Text for state {state}"
            assert str(row[3]) == state

    def test_row_unknown_state_returns_plain_string(self):
        job = SlurmJob(state="WEIRD_STATE")
        row = job.row()
        assert isinstance(row[3], str)
        assert row[3] == "WEIRD_STATE"

    def test_row_state_style_applied(self):
        job = SlurmJob(state="RUNNING")
        row = job.row()
        assert row[3].style == "green"

        job = SlurmJob(state="FAILED")
        row = job.row()
        assert row[3].style == "red bold"


class TestConstants:
    def test_state_styles_covers_queue_states(self):
        for state in QUEUE_STATES:
            assert state in STATE_STYLES, f"{state} missing from STATE_STYLES"

    def test_state_styles_covers_running_states(self):
        for state in RUNNING_STATES:
            assert state in STATE_STYLES, f"{state} missing from STATE_STYLES"

    def test_squeue_fields_match_format(self):
        # SQUEUE_FORMAT has pipe-separated % fields
        field_count = SQUEUE_FORMAT.count("%")
        assert len(SQUEUE_FIELDS) == field_count
