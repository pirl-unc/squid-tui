"""Tests for squidlib.slurm."""

import json
import subprocess
from io import StringIO
from unittest.mock import MagicMock, mock_open, patch

from squidlib.constants import SlurmJob
from squidlib.slurm import (
    cancel_job,
    copy_to_clipboard,
    fetch_completed_jobs,
    fetch_job_detail,
    fetch_job_output_paths,
    fetch_jobs,
    fetch_partitions,
    fetch_recent_history,
    load_config,
    read_file_tail,
    save_config,
)


# ---------------------------------------------------------------------------
# load_config / save_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_valid_json(self, tmp_path):
        config_file = tmp_path / ".squid.json"
        config_file.write_text('{"lists": {"mylist": ["1"]}, "assignments": {}}')
        with patch("squidlib.slurm.CONFIG_PATH", config_file):
            result = load_config()
        assert result == {"lists": {"mylist": ["1"]}, "assignments": {}}

    def test_file_not_found(self, tmp_path):
        config_file = tmp_path / "nonexistent.json"
        with patch("squidlib.slurm.CONFIG_PATH", config_file):
            result = load_config()
        assert result == {"lists": {}, "assignments": {}}

    def test_invalid_json(self, tmp_path):
        config_file = tmp_path / ".squid.json"
        config_file.write_text("not valid json{{{")
        with patch("squidlib.slurm.CONFIG_PATH", config_file):
            result = load_config()
        assert result == {"lists": {}, "assignments": {}}


class TestSaveConfig:
    def test_writes_json_with_permissions(self, tmp_path):
        config_file = tmp_path / ".squid.json"
        with patch("squidlib.slurm.CONFIG_PATH", config_file):
            save_config({"lists": {}, "notes": {}})
        data = json.loads(config_file.read_text())
        assert data == {"lists": {}, "notes": {}}


# ---------------------------------------------------------------------------
# fetch_jobs
# ---------------------------------------------------------------------------

class TestFetchJobs:
    def test_parses_squeue_output(self):
        stdout = "12345|gpu|myjob|alice|RUNNING|1:00:00|2:00:00|4|8G|node01|None\n"
        mock_result = MagicMock(returncode=0, stdout=stdout)
        with patch("squidlib.slurm.subprocess.run", return_value=mock_result) as mock_run:
            jobs = fetch_jobs()
        assert len(jobs) == 1
        assert jobs[0].job_id == "12345"
        assert jobs[0].state == "RUNNING"
        assert jobs[0].name == "myjob"
        assert "--user" not in mock_run.call_args[0][0]

    def test_passes_user_flag(self):
        mock_result = MagicMock(returncode=0, stdout="")
        with patch("squidlib.slurm.subprocess.run", return_value=mock_result) as mock_run:
            fetch_jobs(user="alice")
        cmd = mock_run.call_args[0][0]
        assert "--user" in cmd
        assert "alice" in cmd

    def test_returns_empty_on_nonzero_exit(self):
        mock_result = MagicMock(returncode=1, stdout="")
        with patch("squidlib.slurm.subprocess.run", return_value=mock_result):
            assert fetch_jobs() == []

    def test_returns_empty_on_file_not_found(self):
        with patch("squidlib.slurm.subprocess.run", side_effect=FileNotFoundError):
            assert fetch_jobs() == []

    def test_returns_empty_on_timeout(self):
        with patch("squidlib.slurm.subprocess.run", side_effect=subprocess.TimeoutExpired("squeue", 10)):
            assert fetch_jobs() == []


# ---------------------------------------------------------------------------
# fetch_completed_jobs
# ---------------------------------------------------------------------------

class TestFetchCompletedJobs:
    def test_empty_input(self):
        assert fetch_completed_jobs(set()) == []

    def test_parses_sacct_output(self):
        stdout = "12345|gpu|myjob|alice|COMPLETED|1:00:00|2:00:00|4|8G|node01\n"
        mock_result = MagicMock(returncode=0, stdout=stdout)
        with patch("squidlib.slurm.subprocess.run", return_value=mock_result):
            jobs = fetch_completed_jobs({"12345"})
        assert len(jobs) == 1
        assert jobs[0].job_id == "12345"
        assert jobs[0].state == "COMPLETED"

    def test_strips_batch_suffix(self):
        stdout = "12345.batch|gpu|myjob|alice|COMPLETED|1:00:00|2:00:00|4|8G|node01\n"
        mock_result = MagicMock(returncode=0, stdout=stdout)
        with patch("squidlib.slurm.subprocess.run", return_value=mock_result):
            jobs = fetch_completed_jobs({"12345"})
        assert len(jobs) == 1
        assert jobs[0].job_id == "12345"

    def test_handles_cancelled_by(self):
        stdout = "12345|gpu|myjob|alice|CANCELLED by 99999|1:00:00|2:00:00|4|8G|node01\n"
        mock_result = MagicMock(returncode=0, stdout=stdout)
        with patch("squidlib.slurm.subprocess.run", return_value=mock_result):
            jobs = fetch_completed_jobs({"12345"})
        assert jobs[0].state == "CANCELLED"

    def test_returns_empty_on_failure(self):
        with patch("squidlib.slurm.subprocess.run", side_effect=FileNotFoundError):
            assert fetch_completed_jobs({"12345"}) == []


# ---------------------------------------------------------------------------
# fetch_recent_history
# ---------------------------------------------------------------------------

class TestFetchRecentHistory:
    def test_filters_active_states(self):
        stdout = (
            "100|gpu|job1|alice|COMPLETED|1:00|2:00|4|8G|node01\n"
            "200|gpu|job2|alice|RUNNING|0:30|2:00|4|8G|node02\n"
            "300|gpu|job3|alice|PENDING|0:00|2:00|4|8G|\n"
        )
        mock_result = MagicMock(returncode=0, stdout=stdout)
        with patch("squidlib.slurm.subprocess.run", return_value=mock_result):
            jobs = fetch_recent_history()
        assert len(jobs) == 1
        assert jobs[0].job_id == "100"
        assert jobs[0].state == "COMPLETED"

    def test_returns_empty_on_failure(self):
        with patch("squidlib.slurm.subprocess.run", side_effect=FileNotFoundError):
            assert fetch_recent_history() == []


# ---------------------------------------------------------------------------
# fetch_job_detail
# ---------------------------------------------------------------------------

class TestFetchJobDetail:
    def test_combines_scontrol_and_sacct(self):
        def side_effect(cmd, **kwargs):
            if cmd[0] == "scontrol":
                return MagicMock(returncode=0, stdout="JobId=12345 Name=test")
            else:
                return MagicMock(returncode=0, stdout="12345|test|gpu|COMPLETED")
        with patch("squidlib.slurm.subprocess.run", side_effect=side_effect):
            result = fetch_job_detail("12345")
        assert "scontrol show job" in result
        assert "sacct" in result

    def test_handles_unavailable_commands(self):
        with patch("squidlib.slurm.subprocess.run", side_effect=FileNotFoundError):
            result = fetch_job_detail("12345")
        assert "unavailable" in result


# ---------------------------------------------------------------------------
# cancel_job
# ---------------------------------------------------------------------------

class TestCancelJob:
    def test_success(self):
        mock_result = MagicMock(returncode=0)
        with patch("squidlib.slurm.subprocess.run", return_value=mock_result):
            success, msg = cancel_job("12345")
        assert success is True
        assert "12345" in msg

    def test_failure(self):
        mock_result = MagicMock(returncode=1, stderr="Permission denied")
        with patch("squidlib.slurm.subprocess.run", return_value=mock_result):
            success, msg = cancel_job("12345")
        assert success is False
        assert "Permission denied" in msg

    def test_file_not_found(self):
        with patch("squidlib.slurm.subprocess.run", side_effect=FileNotFoundError):
            success, msg = cancel_job("12345")
        assert success is False
        assert "not found" in msg


# ---------------------------------------------------------------------------
# fetch_job_output_paths
# ---------------------------------------------------------------------------

class TestFetchJobOutputPaths:
    def test_parses_paths(self):
        stdout = "JobId=12345 StdOut=/home/alice/job.out StdErr=/home/alice/job.err"
        mock_result = MagicMock(returncode=0, stdout=stdout)
        with patch("squidlib.slurm.subprocess.run", return_value=mock_result):
            out, err = fetch_job_output_paths("12345")
        assert out == "/home/alice/job.out"
        assert err == "/home/alice/job.err"

    def test_returns_none_on_failure(self):
        with patch("squidlib.slurm.subprocess.run", side_effect=FileNotFoundError):
            out, err = fetch_job_output_paths("12345")
        assert out is None
        assert err is None

    def test_missing_stderr(self):
        stdout = "JobId=12345 StdOut=/home/alice/job.out"
        mock_result = MagicMock(returncode=0, stdout=stdout)
        with patch("squidlib.slurm.subprocess.run", return_value=mock_result):
            out, err = fetch_job_output_paths("12345")
        assert out == "/home/alice/job.out"
        assert err is None


# ---------------------------------------------------------------------------
# read_file_tail
# ---------------------------------------------------------------------------

class TestReadFileTail:
    def test_returns_content(self):
        mock_result = MagicMock(returncode=0, stdout="line1\nline2\n")
        with patch("squidlib.slurm.subprocess.run", return_value=mock_result):
            assert read_file_tail("/tmp/test.log") == "line1\nline2\n"

    def test_returns_error_on_failure(self):
        mock_result = MagicMock(returncode=1, stderr="No such file")
        with patch("squidlib.slurm.subprocess.run", return_value=mock_result):
            result = read_file_tail("/tmp/missing.log")
        assert "Cannot read" in result


# ---------------------------------------------------------------------------
# copy_to_clipboard
# ---------------------------------------------------------------------------

class TestCopyToClipboard:
    def test_macos(self):
        mock_result = MagicMock(returncode=0)
        with patch("squidlib.slurm.platform.system", return_value="Darwin"), \
             patch("squidlib.slurm.subprocess.run", return_value=mock_result) as mock_run:
            success, msg = copy_to_clipboard("12345")
        assert success is True
        assert "12345" in msg
        assert mock_run.call_args[0][0] == ["pbcopy"]

    def test_linux_xclip(self):
        mock_result = MagicMock(returncode=0)
        with patch("squidlib.slurm.platform.system", return_value="Linux"), \
             patch("squidlib.slurm.shutil.which", side_effect=lambda x: "/usr/bin/xclip" if x == "xclip" else None), \
             patch("squidlib.slurm.subprocess.run", return_value=mock_result) as mock_run:
            success, msg = copy_to_clipboard("test")
        assert success is True
        assert mock_run.call_args[0][0] == ["xclip", "-selection", "clipboard"]

    def test_no_clipboard_tool(self):
        with patch("squidlib.slurm.platform.system", return_value="Linux"), \
             patch("squidlib.slurm.shutil.which", return_value=None):
            success, msg = copy_to_clipboard("test")
        assert success is False
        assert "No clipboard tool" in msg


# ---------------------------------------------------------------------------
# fetch_partitions
# ---------------------------------------------------------------------------

class TestFetchPartitions:
    def test_parses_sinfo_output(self):
        stdout = "gpu*|up|7-00:00:00|4|96/288/0/384|192000\ncpu|up|1-00:00:00|8|64/448/0/512|131072\n"
        mock_result = MagicMock(returncode=0, stdout=stdout)
        with patch("squidlib.slurm.subprocess.run", return_value=mock_result):
            parts = fetch_partitions()
        assert len(parts) == 2
        assert parts[0]["partition"] == "gpu*"
        assert parts[1]["avail"] == "up"

    def test_returns_empty_on_failure(self):
        with patch("squidlib.slurm.subprocess.run", side_effect=FileNotFoundError):
            assert fetch_partitions() == []
