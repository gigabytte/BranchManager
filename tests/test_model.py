"""Tests for the model module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from branch_manager.model import AppConfig, ConfigError, GitHubConfig


class TestGitHubConfig:
    """Test cases for GitHubConfig."""

    def test_github_config_default_values(self):
        """Test GitHubConfig with default values."""
        config = GitHubConfig(organization="test-org")

        assert config.organization == "test-org"
        assert config.included_repo_regex == ".*"
        assert config.exempt_authors_regex == "^$"
        assert config.exempt_branches_regex == "^$"
        assert config.days_before_branch_stale == 30
        assert config.days_before_branch_delete == 60

    def test_github_config_custom_values(self):
        """Test GitHubConfig with custom values."""
        config = GitHubConfig(
            organization="custom-org",
            included_repo_regex="^test.*",
            exempt_authors_regex="^bot-.*",
            exempt_branches_regex="^(main|master|develop)$",
            days_before_branch_stale=14,
            days_before_branch_delete=28,
        )

        assert config.organization == "custom-org"
        assert config.included_repo_regex == "^test.*"
        assert config.exempt_authors_regex == "^bot-.*"
        assert config.exempt_branches_regex == "^(main|master|develop)$"
        assert config.days_before_branch_stale == 14
        assert config.days_before_branch_delete == 28

    def test_github_config_with_aliases(self):
        """Test GitHubConfig using field aliases."""
        data = {
            "organization": "test-org",
            "included-repo-regex": "^api-.*",
            "exempt-authors-regex": "^dependabot.*",
            "exempt-branches-regex": "^release.*",
            "days-before-branch-stale": 21,
            "days-before-branch-delete": 42,
        }

        config = GitHubConfig.model_validate(data)

        assert config.organization == "test-org"
        assert config.included_repo_regex == "^api-.*"
        assert config.exempt_authors_regex == "^dependabot.*"
        assert config.exempt_branches_regex == "^release.*"
        assert config.days_before_branch_stale == 21
        assert config.days_before_branch_delete == 42

    def test_github_config_mixed_field_names_and_aliases(self):
        """Test GitHubConfig with mix of field names and aliases."""
        data = {
            "organization": "test-org",
            "included_repo_regex": "^service-.*",  # field name
            "exempt-authors-regex": "^bot.*",  # alias
            "exempt_branches_regex": "^main$",  # field name
            "days-before-branch-stale": 7,  # alias
            "days_before_branch_delete": 14,  # field name
        }

        config = GitHubConfig.model_validate(data)

        assert config.organization == "test-org"
        assert config.included_repo_regex == "^service-.*"
        assert config.exempt_authors_regex == "^bot.*"
        assert config.exempt_branches_regex == "^main$"
        assert config.days_before_branch_stale == 7
        assert config.days_before_branch_delete == 14

    def test_github_config_invalid_regex_patterns(self):
        """Test GitHubConfig with invalid regex patterns."""
        # Invalid included_repo_regex
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            GitHubConfig(organization="test", included_repo_regex="[invalid")

        # Invalid exempt_authors_regex
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            GitHubConfig(organization="test", exempt_authors_regex="(unclosed")

        # Invalid exempt_branches_regex
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            GitHubConfig(organization="test", exempt_branches_regex="*invalid")

    def test_github_config_days_validation(self):
        """Test GitHubConfig day validation."""
        # Test minimum values
        with pytest.raises(ValueError):
            GitHubConfig(organization="test", days_before_branch_stale=0)

        with pytest.raises(ValueError):
            GitHubConfig(organization="test", days_before_branch_delete=0)

        # Test negative values
        with pytest.raises(ValueError):
            GitHubConfig(organization="test", days_before_branch_stale=-1)

        with pytest.raises(ValueError):
            GitHubConfig(organization="test", days_before_branch_delete=-1)

    def test_github_config_days_order_validation(self):
        """Test that delete days must be >= stale days."""
        # Valid: delete >= stale
        config = GitHubConfig(
            organization="test", days_before_branch_stale=30, days_before_branch_delete=30
        )
        assert config.days_before_branch_stale == 30
        assert config.days_before_branch_delete == 30

        # Valid: delete > stale
        config = GitHubConfig(
            organization="test", days_before_branch_stale=30, days_before_branch_delete=60
        )
        assert config.days_before_branch_stale == 30
        assert config.days_before_branch_delete == 60

        # Invalid: delete < stale
        with pytest.raises(
            ValueError, match="days_before_branch_delete must be >= days_before_branch_stale"
        ):
            GitHubConfig(
                organization="test", days_before_branch_stale=60, days_before_branch_delete=30
            )

    def test_github_config_extra_fields_forbidden(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            GitHubConfig.model_validate({"organization": "test", "unknown_field": "value"})

    def test_github_config_required_organization(self):
        """Test that organization field is required."""
        with pytest.raises(ValueError, match="Field required"):
            GitHubConfig.model_validate({})

    def test_github_config_valid_regex_patterns(self):
        """Test GitHubConfig with various valid regex patterns."""
        valid_patterns = [
            ".*",  # match all
            "^$",  # match empty
            "^test.*",  # starts with test
            ".*test$",  # ends with test
            "(api|web)-.*",  # starts with api- or web-
            "^(main|master|develop)$",  # exact matches
            "[a-z]+",  # character class
            "\\d+",  # digits
        ]

        for pattern in valid_patterns:
            config = GitHubConfig(
                organization="test",
                included_repo_regex=pattern,
                exempt_authors_regex=pattern,
                exempt_branches_regex=pattern,
            )
            assert config.included_repo_regex == pattern
            assert config.exempt_authors_regex == pattern
            assert config.exempt_branches_regex == pattern


class TestConfig:
    """Test cases for Config."""

    def test_config_default_values(self):
        """Test Config with default values."""
        config = AppConfig()

        assert config.github == []
        assert isinstance(config.github, list)

    def test_config_with_github_configs(self):
        """Test Config with GitHub configurations."""
        github_configs = [
            GitHubConfig(organization="org1"),
            GitHubConfig(organization="org2", days_before_branch_stale=14),
        ]

        config = AppConfig(github=github_configs)

        assert len(config.github) == 2
        assert config.github[0].organization == "org1"
        assert config.github[1].organization == "org2"
        assert config.github[1].days_before_branch_stale == 14

    def test_config_from_env(self):
        """Test Config.from_env() class method."""
        config = AppConfig.from_env()

        assert isinstance(config, AppConfig)
        assert config.github == []
        assert not config.has_github_configs()

    def test_config_get_github_configs(self):
        """Test Config.get_github_configs() method."""
        github_configs = [GitHubConfig(organization="org1"), GitHubConfig(organization="org2")]

        config = AppConfig(github=github_configs)
        retrieved_configs = config.get_github_configs()

        assert retrieved_configs == github_configs
        assert len(retrieved_configs) == 2

    def test_config_has_github_configs(self):
        """Test Config.has_github_configs() method."""
        # Empty config
        config = AppConfig()
        assert not config.has_github_configs()

        # Config with GitHub configurations
        config = AppConfig(github=[GitHubConfig(organization="test")])
        assert config.has_github_configs()

    def test_config_extra_fields_forbidden(self):
        """Test that extra fields are forbidden in Config."""
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            AppConfig.model_validate({"github": [], "unknown_field": "value"})

    def test_config_from_yaml_file_success(self):
        """Test successful loading from YAML file."""
        yaml_content = """
github:
  - organization: test-org
    included-repo-regex: "^api-.*"
    days-before-branch-stale: 14
    days-before-branch-delete: 28
  - organization: another-org
    exempt-authors-regex: "^bot.*"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            config = AppConfig.from_yaml_file(temp_path)

            assert len(config.github) == 2
            assert config.github[0].organization == "test-org"
            assert config.github[0].included_repo_regex == "^api-.*"
            assert config.github[0].days_before_branch_stale == 14
            assert config.github[0].days_before_branch_delete == 28
            assert config.github[1].organization == "another-org"
            assert config.github[1].exempt_authors_regex == "^bot.*"
        finally:
            Path(temp_path).unlink()

    def test_config_from_yaml_file_not_found(self):
        """Test from_yaml_file with non-existent file."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            AppConfig.from_yaml_file("/non/existent/file.yaml")

    def test_config_from_yaml_file_not_a_file(self):
        """Test from_yaml_file with a directory instead of file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError, match="Path is not a file"):
                AppConfig.from_yaml_file(temp_dir)

    def test_config_from_yaml_file_empty_file(self):
        """Test from_yaml_file with empty file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")  # Empty file
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Empty configuration file"):
                AppConfig.from_yaml_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_config_from_yaml_file_invalid_yaml(self):
        """Test from_yaml_file with invalid YAML."""
        invalid_yaml = """
github:
  - organization: test
    invalid: [unclosed
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(invalid_yaml)
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid YAML"):
                AppConfig.from_yaml_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_config_from_yaml_file_invalid_config(self):
        """Test from_yaml_file with invalid configuration."""
        invalid_config = """
github:
  - organization: test
    days-before-branch-stale: -1  # Invalid: must be >= 1
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(invalid_config)
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid configuration"):
                AppConfig.from_yaml_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_config_from_yaml_file_with_pathlib_path(self):
        """Test from_yaml_file with pathlib.Path object."""
        yaml_content = """
github:
  - organization: test-org
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            config = AppConfig.from_yaml_file(temp_path)
            assert len(config.github) == 1
            assert config.github[0].organization == "test-org"
        finally:
            temp_path.unlink()

    @patch("builtins.open", side_effect=OSError("Permission denied"))
    def test_config_from_yaml_file_read_error(self, mock_open):
        """Test from_yaml_file with file read error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Empty configuration file"):
                AppConfig.from_yaml_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_config_yaml_file_only_whitespace(self):
        """Test from_yaml_file with file containing only whitespace."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("   \n\t  \n  ")  # Only whitespace
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid YAML"):
                AppConfig.from_yaml_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_config_minimal_valid_yaml(self):
        """Test from_yaml_file with minimal valid YAML."""
        yaml_content = """
github: []
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            config = AppConfig.from_yaml_file(temp_path)
            assert config.github == []
            assert not config.has_github_configs()
        finally:
            Path(temp_path).unlink()

    def test_config_complex_yaml_structure(self):
        """Test from_yaml_file with complex YAML structure."""
        yaml_content = """
github:
  - organization: "org-1"
    included-repo-regex: "^(api|web|mobile)-.*"
    exempt-authors-regex: "^(dependabot|renovate)\\\\[bot\\\\]$"
    exempt-branches-regex: "^(main|master|develop|release/.*)$"
    days-before-branch-stale: 7
    days-before-branch-delete: 14
  - organization: "org-2"
    included-repo-regex: ".*"
    exempt-authors-regex: "^bot-.*"
    exempt-branches-regex: "^$"
    days-before-branch-stale: 30
    days-before-branch-delete: 90
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            config = AppConfig.from_yaml_file(temp_path)

            assert len(config.github) == 2

            # Validate first org
            org1 = config.github[0]
            assert org1.organization == "org-1"
            assert org1.included_repo_regex == "^(api|web|mobile)-.*"
            assert org1.exempt_authors_regex == "^(dependabot|renovate)\\[bot\\]$"
            assert org1.exempt_branches_regex == "^(main|master|develop|release/.*)$"
            assert org1.days_before_branch_stale == 7
            assert org1.days_before_branch_delete == 14

            # Validate second org
            org2 = config.github[1]
            assert org2.organization == "org-2"
            assert org2.included_repo_regex == ".*"
            assert org2.exempt_authors_regex == "^bot-.*"
            assert org2.exempt_branches_regex == "^$"
            assert org2.days_before_branch_stale == 30
            assert org2.days_before_branch_delete == 90

        finally:
            Path(temp_path).unlink()


class TestConfigError:
    """Test cases for ConfigError."""

    def test_config_error_is_exception(self):
        """Test that ConfigError is an Exception."""
        assert issubclass(ConfigError, Exception)

    def test_config_error_can_be_raised(self):
        """Test that ConfigError can be raised and caught."""
        with pytest.raises(ConfigError):
            raise ConfigError("Test error message")

    def test_config_error_with_message(self):
        """Test ConfigError with custom message."""
        message = "Custom configuration error"
        try:
            raise ConfigError(message)
        except ConfigError as e:
            assert str(e) == message
