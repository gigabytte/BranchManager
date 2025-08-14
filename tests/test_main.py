"""Test suite for the main module using table-driven tests."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from branch_manager.main import get_access_token, main, runner
from branch_manager.model import AppConfig, ConfigError, GitHubConfig


class TestGetAccessToken:
    """Test cases for get_access_token function."""

    @pytest.mark.parametrize(
        "env_vars,expected",
        [
            # Test cases: (environment_variables, expected_result)
            ({"ACCESS_TOKEN": "test_token_123"}, "test_token_123"),
            ({"ACCESS_TOKEN": ""}, None),
            ({}, None),
            ({"OTHER_VAR": "value"}, None),
            ({"ACCESS_TOKEN": "ghp_1234567890abcdef"}, "ghp_1234567890abcdef"),
        ],
    )
    def test_get_access_token(self, env_vars, expected):
        """Test access token retrieval from environment variables."""
        with patch.dict(os.environ, env_vars, clear=True):
            result = get_access_token()
            assert result == expected


class TestMainCommand:
    """Test cases for the main CLI command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @pytest.mark.parametrize(
        "cli_args,expected_verbose,expected_dry_run,expected_exit_code",
        [
            # Test cases: (cli_arguments, verbose_flag, dry_run_flag, expected_exit_code)
            ([], False, False, 1),  # No access token - should fail
            (["--verbose"], True, False, 1),  # Verbose but no token - should fail
            (["--dry-run"], False, True, 1),  # Dry run but no token - should fail
            (["--verbose", "--dry-run"], True, True, 1),  # Both flags but no token - should fail
            (["-v"], True, False, 1),  # Short verbose flag
            (["-d"], False, True, 1),  # Short dry-run flag
            (["-v", "-d"], True, True, 1),  # Both short flags
        ],
    )
    def test_main_command_without_token(
        self, cli_args, expected_verbose, expected_dry_run, expected_exit_code
    ):
        """Test main command behavior without access token."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("github:\n  - organization: test-org\n")
            config_path = f.name

        try:
            with patch.dict(os.environ, {}, clear=True):
                result = self.runner.invoke(main, cli_args + ["--config", config_path])
                assert result.exit_code == expected_exit_code
                assert "Access token not found" in result.output
        finally:
            Path(config_path).unlink()

    @pytest.mark.parametrize(
        "cli_args,env_vars,expected_exit_code,expected_output_contains",
        [
            # Test cases: (cli_args, environment_vars, exit_code, output_should_contain)
            (
                [],
                {"ACCESS_TOKEN": "test_token"},
                0,
                ["🍞 BranchManager 🗑️", "Processing github with"],
            ),
            (
                ["--verbose"],
                {"ACCESS_TOKEN": "test_token"},
                0,
                ["Verbose mode enabled", "Access token found"],
            ),
            (
                ["--dry-run"],
                {"ACCESS_TOKEN": "test_token"},
                0,
                ["Dry run mode enabled", "no changes will be made"],
            ),
            (
                ["-v", "-d"],
                {"ACCESS_TOKEN": "test_token"},
                0,
                ["Verbose mode enabled", "Dry run mode enabled"],
            ),
        ],
    )
    @patch("branch_manager.main.runner")
    def test_main_command_with_token(
        self, mock_runner, cli_args, env_vars, expected_exit_code, expected_output_contains
    ):
        """Test main command behavior with access token."""
        mock_runner.return_value = None

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("github:\n  - organization: test-org\n")
            config_path = f.name

        try:
            with patch.dict(os.environ, env_vars, clear=True):
                result = self.runner.invoke(main, cli_args + ["--config", config_path])

                for expected_text in expected_output_contains:
                    assert expected_text in result.output

                assert result.exit_code == expected_exit_code
        finally:
            Path(config_path).unlink()

    @pytest.mark.parametrize(
        "config_content,expected_exit_code,expected_error",
        [
            # Test cases: (yaml_config_content, exit_code, error_message_contains)
            ("invalid: yaml: content: [", 1, "Configuration Error"),
            ("github: invalid_structure", 1, "Configuration Error"),
        ],
    )
    @patch("branch_manager.main.runner")
    def test_main_with_config_file(
        self, mock_runner, config_content, expected_exit_code, expected_error
    ):
        """Test main command with various config file contents."""
        mock_runner.return_value = None

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            with patch.dict(os.environ, {"ACCESS_TOKEN": "test_token"}, clear=True):
                result = self.runner.invoke(main, ["--config", config_path])
                assert result.exit_code == expected_exit_code

                if expected_error:
                    assert expected_error in result.output
        finally:
            Path(config_path).unlink()

    def test_main_with_empty_config_file(self):
        """Test main command with empty config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")  # Empty file
            config_path = f.name

        try:
            with patch.dict(os.environ, {"ACCESS_TOKEN": "test_token"}, clear=True):
                with patch("branch_manager.main.runner") as mock_runner:
                    mock_runner.return_value = None
                    result = self.runner.invoke(main, ["--config", config_path])

                    # Empty config file should cause an error
                    assert result.exit_code == 1
                    assert "Empty configuration file" in result.output
        finally:
            Path(config_path).unlink()

    def test_main_with_empty_github_array(self):
        """Test main command with empty GitHub array in config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("github: []")
            config_path = f.name

        try:
            with patch.dict(os.environ, {"ACCESS_TOKEN": "test_token"}, clear=True):
                with patch("branch_manager.main.runner") as mock_runner:
                    mock_runner.return_value = None
                    result = self.runner.invoke(main, ["--config", config_path])
                    # Should succeed with empty github array since runner is mocked
                    assert result.exit_code == 0
                    assert "🍞 BranchManager 🗑️" in result.output
        finally:
            Path(config_path).unlink()

    def test_main_with_nonexistent_config_file(self):
        """Test main command with non-existent config file."""
        result = self.runner.invoke(main, ["--config", "/nonexistent/file.yaml"])
        assert result.exit_code == 2  # Click's exit code for bad parameter

    @pytest.mark.parametrize(
        "exception_type,verbose_flag,should_show_traceback",
        [
            # Test cases: (exception_to_raise, verbose_mode, expect_traceback_in_output)
            (ConfigError("Test config error"), False, False),
            (ConfigError("Test config error"), True, False),  # Config errors don't show traceback
            (FileNotFoundError("File not found"), False, False),
            (FileNotFoundError("File not found"), True, False),  # Known errors don't show traceback
            (ValueError("Test value error"), False, False),
            (ValueError("Test value error"), True, False),  # Known errors don't show traceback
            (RuntimeError("Unexpected error"), False, False),
            (RuntimeError("Unexpected error"), True, True),  # Only unexpected errors show traceback
        ],
    )
    @patch("branch_manager.main.AppConfig.from_yaml_file")
    def test_main_exception_handling(
        self, mock_config, exception_type, verbose_flag, should_show_traceback
    ):
        """Test main command exception handling."""
        mock_config.side_effect = exception_type

        cli_args = ["--verbose"] if verbose_flag else []

        with patch.dict(os.environ, {"ACCESS_TOKEN": "test_token"}, clear=True):
            result = self.runner.invoke(main, cli_args)
            assert result.exit_code == 1

            if should_show_traceback:
                assert "Traceback" in result.output or "Exception" in result.output

            if isinstance(exception_type, ConfigError | FileNotFoundError | ValueError):
                assert "Configuration Error" in result.output
            else:
                assert "Unexpected error" in result.output

    def test_version_option(self):
        """Test --version option."""
        result = self.runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "branch-manager" in result.output


class TestRunnerFunction:
    """Test cases for the runner function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock(spec=AppConfig)
        self.mock_git_config = Mock(spec=GitHubConfig)
        self.mock_git_config.organization = "test-org"

    @pytest.mark.parametrize(
        "process_org_results,expected_warning",
        [
            # Test cases: (organization_results, expected_warning_message)
            ({"repos": 1, "deleted": 0, "notified": 1, "skipped": 0, "errors": 0}, None),
            ({"repos": 0, "deleted": 0, "notified": 0, "skipped": 0, "errors": 0}, None),
        ],
    )
    @patch("branch_manager.main.warn")
    def test_runner_basic_functionality(self, mock_warn, process_org_results, expected_warning):
        """Test runner basic functionality with mock client."""
        mock_client = Mock()
        mock_client.process_organization.return_value = process_org_results
        mock_client.close.return_value = None

        mock_org_config = Mock(spec=GitHubConfig)
        mock_org_config.organization = "test-org"

        result = runner(mock_client, mock_org_config, False)

        mock_client.process_organization.assert_called_once_with(
            org_name="test-org", config=mock_org_config, dry_run=False
        )
        mock_client.close.assert_called_once()

        if expected_warning:
            mock_warn.assert_called_with(expected_warning)

        assert result is None

    @pytest.mark.parametrize(
        "org_results,dry_run,expected_summary",
        [
            # Test cases: (organization_results, dry_run_mode, expected_summary_totals)
            (
                {"repos": 2, "deleted": 1, "notified": 3, "skipped": 0, "errors": 0},
                False,
                {"repos": 2, "deleted": 1, "notified": 3, "skipped": 0, "errors": 0},
            ),
            (
                {"repos": 1, "deleted": 0, "notified": 0, "skipped": 0, "errors": 2},
                True,
                {"repos": 1, "deleted": 0, "notified": 0, "skipped": 0, "errors": 2},
            ),
        ],
    )
    @patch("branch_manager.main.info")
    @patch("branch_manager.main.warn")
    def test_runner_summary_reporting(
        self, mock_warn, mock_info, org_results, dry_run, expected_summary
    ):
        """Test runner summary reporting functionality."""
        mock_client = Mock()
        mock_client.process_organization.return_value = org_results
        mock_client.close.return_value = None

        mock_org_config = Mock(spec=GitHubConfig)
        mock_org_config.organization = "test-org"

        runner(mock_client, mock_org_config, dry_run)

        mock_client.process_organization.assert_called_once_with(
            org_name="test-org", config=mock_org_config, dry_run=dry_run
        )
        mock_client.close.assert_called_once()

        # Check that summary is logged
        assert any("Processing Summary:" in str(call) for call in mock_info.call_args_list)

        # Check error warning if errors > 0
        if expected_summary["errors"] > 0:
            assert any("Errors encountered:" in str(call) for call in mock_warn.call_args_list)

    @pytest.mark.parametrize(
        "dry_run",
        [
            # Test cases: (dry_run_setting)
            (True,),
            (False,),
        ],
    )
    def test_runner_with_dry_run_flag(self, dry_run):
        """Test runner behavior with different dry_run settings."""
        mock_client = Mock()
        mock_client.process_organization.return_value = {
            "repos": 1,
            "deleted": 0,
            "notified": 1,
            "skipped": 0,
            "errors": 0,
        }
        mock_client.close.return_value = None

        mock_org_config = Mock(spec=GitHubConfig)
        mock_org_config.organization = "test-org"

        result = runner(mock_client, mock_org_config, dry_run)

        mock_client.process_organization.assert_called_once_with(
            org_name="test-org", config=mock_org_config, dry_run=dry_run
        )
        mock_client.close.assert_called_once()
        assert result is None


class TestIntegration:
    """Integration tests combining multiple components."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.runner = CliRunner()

    @pytest.mark.parametrize(
        "config_yaml,env_vars,cli_args,expected_messages",
        [
            # Test cases: (yaml_config, environment, cli_arguments, expected_output_messages)
            (
                """
github:
  - organization: test-org
    included-repo-regex: "^test-"
    exempt-authors-regex: "^dependabot"
    exempt-branches-regex: "^(main|master)$"
    days-before-branch-stale: 30
    days-before-branch-delete: 60
                """,
                {"ACCESS_TOKEN": "ghp_test123"},
                ["--verbose", "--dry-run"],
                ["Verbose mode enabled", "Dry run mode enabled", "Processing github with"],
            ),
            (
                """
github: []
                """,
                {"ACCESS_TOKEN": "ghp_test123"},
                [],
                ["🍞 BranchManager 🗑️", "Loading configuration from:"],
            ),
        ],
    )
    @patch("branch_manager.main.runner")
    def test_full_integration(
        self, mock_runner, config_yaml, env_vars, cli_args, expected_messages
    ):
        """Test full integration from CLI to runner."""
        mock_runner.return_value = None

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_yaml)
            config_path = f.name

        try:
            full_args = cli_args + ["--config", config_path]

            with patch.dict(os.environ, env_vars, clear=True):
                result = self.runner.invoke(main, full_args)

                for message in expected_messages:
                    assert message in result.output

        finally:
            Path(config_path).unlink()
