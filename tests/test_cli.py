"""Tests for squidlib.cli.cli_main."""

import os
import sys
from unittest.mock import patch

import pytest


class TestCliArgs:
    def test_default_user_is_env_user(self):
        with patch.dict(os.environ, {"USER": "testuser"}), \
             patch("squidlib.cli.cli_main.app_run") as mock_run:
            from squidlib.cli.cli_main import run
            with patch("sys.argv", ["squid"]):
                run()
        mock_run.assert_called_once_with(user="testuser", refresh_interval=180)

    def test_all_flag_sets_user_none(self):
        with patch("squidlib.cli.cli_main.app_run") as mock_run:
            from squidlib.cli.cli_main import run
            with patch("sys.argv", ["squid", "--all"]):
                run()
        mock_run.assert_called_once_with(user=None, refresh_interval=180)

    def test_user_override(self):
        with patch("squidlib.cli.cli_main.app_run") as mock_run:
            from squidlib.cli.cli_main import run
            with patch("sys.argv", ["squid", "--user", "bob"]):
                run()
        mock_run.assert_called_once_with(user="bob", refresh_interval=180)

    def test_refresh_override(self):
        with patch.dict(os.environ, {"USER": "testuser"}), \
             patch("squidlib.cli.cli_main.app_run") as mock_run:
            from squidlib.cli.cli_main import run
            with patch("sys.argv", ["squid", "--refresh", "60"]):
                run()
        mock_run.assert_called_once_with(user="testuser", refresh_interval=60)

    def test_version_flag(self):
        with pytest.raises(SystemExit) as exc_info:
            from squidlib.cli.cli_main import run
            with patch("sys.argv", ["squid", "--version"]):
                run()
        assert exc_info.value.code == 0
