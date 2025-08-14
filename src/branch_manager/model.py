"""Configuration management for branch-manager."""

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class GitPlatformConfig(BaseModel):
    """Configuration for any Git platform organization."""

    organization: str = Field(..., description="Organization name")
    included_repo_regex: str = Field(
        default=".*",
        description="Regex pattern for repositories to include",
        alias="included-repo-regex",
    )
    exempt_authors_regex: str = Field(
        default="^$",
        description="Regex pattern for authors to exempt from stale checks",
        alias="exempt-authors-regex",
    )
    exempt_branches_regex: str = Field(
        default="^$",
        description="Regex pattern for branches to exempt from stale checks",
        alias="exempt-branches-regex",
    )
    days_before_branch_stale: int = Field(
        default=30,
        ge=1,
        description="Days before a branch is considered stale",
        alias="days-before-branch-stale",
    )
    days_before_branch_delete: int = Field(
        default=60,
        ge=1,
        description="Days before a stale branch is deleted",
        alias="days-before-branch-delete",
    )
    access_token_environment_variable: str = Field(
        default="ACCESS_TOKEN",
        description="Environment variable name for access token",
        alias="access-token-environment-variable",
    )

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator(
        "included_repo_regex",
        "exempt_authors_regex",
        "exempt_branches_regex",
    )
    @classmethod
    def validate_regex(cls, v: str) -> str:
        """Validate that regex patterns are valid."""
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{v}': {e}") from e
        return v

    @model_validator(mode="after")
    def validate_days_order(self) -> "GitPlatformConfig":
        """Validate that delete days is greater than or equal to stale days."""
        if self.days_before_branch_delete < self.days_before_branch_stale:
            raise ValueError("days_before_branch_delete must be >= days_before_branch_stale")
        return self


# Platform-specific aliases for better type hinting
GitHubConfig = GitPlatformConfig


class AppConfig(BaseModel):
    """Main application configuration supporting multiple Git platforms."""

    github: list[GitHubConfig] = Field(
        default_factory=list, description="List of GitHub organization configurations"
    )

    model_config = {"extra": "forbid"}

    @classmethod
    def from_yaml_file(cls, file_path: str | Path) -> "AppConfig":
        """Load configuration from a YAML file.

        Args:
            file_path: Path to the YAML configuration file

        Returns:
            AppConfig instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the YAML is invalid or doesn't match schema
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {path}: {e}") from e
        except Exception as e:
            raise ValueError(f"Error reading file {path}: {e}") from e

        if data is None:
            raise ValueError(f"Empty configuration file: {path}")

        try:
            return cls.model_validate(data)
        except Exception as e:
            raise ValueError(f"Invalid configuration in {path}: {e}") from e

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create configuration from environment variables.

        Returns:
            AppConfig instance with empty configurations
        """
        return cls()

    # Platform-specific methods
    def get_github_configs(self) -> list[GitHubConfig]:
        """Get all GitHub configurations."""
        return self.github

    # Generic methods for all platforms
    def get_all_platform_configs(self) -> dict[str, list[GitPlatformConfig]]:
        """Get configurations for all platforms.

        Returns:
            Dictionary mapping platform names to their configurations
        """
        return {"github": self.github}

    def get_platform_configs(self, platform: str) -> list[GitPlatformConfig]:
        """Get configurations for a specific platform.

        Args:
            platform: Platform name ('github' .. etc)

        Returns:
            List of configurations for the platform

        Raises:
            ValueError: If platform is not supported
        """
        platform_lower = platform.lower()
        if platform_lower == "github":
            return self.github
        else:
            raise ValueError(f"Unsupported platform: {platform}")

    def has_platform_configs(self, platform: str) -> bool:
        """Check if any configurations exist for a platform.

        Args:
            platform: Platform name ('github', 'bitbucket', 'gitlab')

        Returns:
            True if configurations exist for the platform
        """
        try:
            return len(self.get_platform_configs(platform)) > 0
        except ValueError:
            return False

    def has_any_configs(self) -> bool:
        """Check if any configurations are defined for any platform."""
        return len(self.github) > 0

    def get_supported_platforms(self) -> list[str]:
        """Get list of platforms that have configurations."""
        platforms = []
        if self.github:
            platforms.append("github")
        return platforms

    def has_github_configs(self) -> bool:
        """Check if any GitHub configurations are defined."""
        return len(self.github) > 0


class ConfigError(Exception):
    """Configuration-related errors."""

    pass
