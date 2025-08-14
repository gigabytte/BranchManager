# Configuration API Reference

This document describes the configuration models and API for branch-manager.

## Overview

The configuration system uses Pydantic models to validate and
parse YAML configuration files. The main entry point is the `AppConfig`
class which contains lists of platform-specific configuration objects.
Currently supports GitHub with extensible design for additional Git platforms.

## Classes

### `GitPlatformConfig`

Base configuration class for any Git platform organization's
branch management settings. This is the foundation for
platform-specific configurations.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `organization` | `str` | **Yes** | - | Organization name |
| `included-repo-regex` | `str` | No | `".*"` | Regex pattern for repositories to include |
| `exempt-authors-regex` | `str` | No | `"^$"` | Regex pattern for authors to exempt from stale checks |
| `exempt-branches-regex` | `str` | No | `"^$"` | Regex pattern for branches to exempt from stale checks |
| `days-before-branch-stale` | `int` | No | `30` | Days before a branch is considered stale (≥1) |
| `days-before-branch-delete` | `int` | No | `60` | Days before a stale branch is deleted (≥1) |
| `access-token-environment-variable` | `str` | No | `"ACCESS_TOKEN"` | Environment variable name for access token |

### `GitHubConfig`

Platform-specific configuration for GitHub organizations.
This is an alias for `GitPlatformConfig` with GitHub-specific defaults.

### `GitHubConfig`

Platform-specific configuration for GitHub organizations.
This is an alias for `GitPlatformConfig` with GitHub-specific defaults.

#### Fields

Inherits all fields from `GitPlatformConfig`.
See `GitPlatformConfig` section above for complete field documentation.

#### Validation Rules

- All regex patterns must be valid regular expressions
- `days-before-branch-delete` must be ≥ `days-before-branch-stale`
- Both day values must be ≥ 1
- No additional fields are allowed (`extra="forbid"`)

#### Example

```python
from branch_manager.model import GitHubConfig

config = GitHubConfig(
    organization="gigabytte",
    included_repo_regex="^tst-",
    exempt_authors_regex="^dependabot",
    exempt_branches_regex="^(main|master|release)$",
    days_before_branch_stale=30,
    days_before_branch_delete=60,
    access_token_environment_variable="GITHUB_TOKEN"
)
```

### `AppConfig`

Main configuration class that contains all Git platform configurations. Supports multiple platforms with extensible design.

### `AppConfig`

Main configuration class that contains all Git platform configurations. Supports multiple platforms with extensible design.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `github` | `list[GitHubConfig]` | No | `[]` | List of GitHub organization configurations |

#### Methods

##### `from_yaml_file(file_path: str | Path) -> AppConfig`

**Class method** - Load configuration from a YAML file.

**Parameters:**

- `file_path` (`str | Path`): Path to the YAML configuration file

**Returns:**

- `AppConfig`: Validated configuration instance

**Raises:**

- `FileNotFoundError`: If the file doesn't exist
- `ValueError`: If the YAML is invalid or doesn't match schema

**Example:**

```python
from branch_manager.model import AppConfig

config = AppConfig.from_yaml_file("config.yaml")
```

##### `from_env() -> AppConfig`

**Class method** - Create configuration from environment variables.

**Returns:**

- `AppConfig`: Empty configuration instance with default GitHub configuration

**Example:**

```python
from branch_manager.model import AppConfig

config = AppConfig.from_env()
```

##### `get_github_configs() -> list[GitHubConfig]`

Get all GitHub configurations.

**Returns:**

- `list[GitHubConfig]`: List of GitHub configurations

**Example:**

```python
github_configs = config.get_github_configs()
for gh_config in github_configs:
    print(f"Organization: {gh_config.organization}")
```

##### `get_all_platform_configs() -> dict[str, list[GitPlatformConfig]]`

Get configurations for all platforms.

**Returns:**

- `dict[str, list[GitPlatformConfig]]`: Dictionary mapping platform names to their configurations

**Example:**

```python
all_configs = config.get_all_platform_configs()
for platform, configs in all_configs.items():
    print(f"Platform {platform} has {len(configs)} configurations")
```

##### `get_platform_configs(platform: str) -> list[GitPlatformConfig]`

Get configurations for a specific platform.

**Parameters:**

- `platform` (`str`): Platform name ('github')

**Returns:**

- `list[GitPlatformConfig]`: List of configurations for the platform

**Raises:**

- `ValueError`: If platform is not supported

**Example:**

```python
github_configs = config.get_platform_configs("github")
```

##### `has_platform_configs(platform: str) -> bool`

Check if any configurations exist for a platform.

**Parameters:**

- `platform` (`str`): Platform name ('github')

**Returns:**

- `bool`: True if configurations exist for the platform

**Example:**

```python
if config.has_platform_configs("github"):
    print("GitHub configurations found")
```

##### `has_any_configs() -> bool`

Check if any configurations are defined for any platform.

**Returns:**

- `bool`: True if any configurations exist

**Example:**

```python
if config.has_any_configs():
    print("Configurations found")
```

##### `get_supported_platforms() -> list[str]`

Get list of platforms that have configurations.

**Returns:**

- `list[str]`: List of platform names with configurations

**Example:**

```python
platforms = config.get_supported_platforms()
print(f"Configured platforms: {platforms}")
```

##### `has_github_configs() -> bool`

Check if any GitHub configurations are defined.

**Returns:**

- `bool`: True if GitHub configurations exist

**Example:**

```python
if config.has_github_configs():
    print("GitHub configurations found")
```

### `ConfigError`

Exception class for configuration-related errors.

**Inherits from:** `Exception`

**Usage:**

```python
from branch_manager.model import ConfigError

try:
    config = AppConfig.from_yaml_file("invalid.yaml")
except ConfigError as e:
    print(f"Configuration error: {e}")
```

## YAML Configuration Format

### Structure

```yaml
github:
  - organization: string
    included-repo-regex: string (optional)
    exempt-authors-regex: string (optional)
    exempt-branches-regex: string (optional)
    days-before-branch-stale: integer (optional)
    days-before-branch-delete: integer (optional)
    access-token-environment-variable: string (optional)
```

### Example Configuration

```yaml
github:
  - organization: gigabytte
    included-repo-regex: ^tst-
    exempt-authors-regex: ^dependabot
    exempt-branches-regex: ^(main|master|release)$
    days-before-branch-stale: 30
    days-before-branch-delete: 60
    access-token-environment-variable: GITHUB_TOKEN
```

### Multiple Organizations

```yaml
github:
  - organization: org1
    included-repo-regex: ^test-
    days-before-branch-stale: 14
    days-before-branch-delete: 30
    access-token-environment-variable: ORG1_TOKEN
  - organization: org2
    included-repo-regex: ^CLOUD-
    exempt-authors-regex: ^(dependabot|renovate)
    days-before-branch-stale: 21
    days-before-branch-delete: 45
    access-token-environment-variable: ORG2_TOKEN
```

## Usage Examples

### Loading Configuration

```python
from branch_manager.model import AppConfig, ConfigError

try:
    # Load from YAML file
    config = AppConfig.from_yaml_file("branches-config.yml")

    # Check if configurations exist
    if config.has_github_configs():
        # Process each GitHub configuration
        for gh_config in config.get_github_configs():
            print(f"Processing org: {gh_config.organization}")
            print(f"Repo filter: {gh_config.included_repo_regex}")
            print(f"Stale after: {gh_config.days_before_branch_stale} days")
            print(f"Token var: {gh_config.access_token_environment_variable}")

    # Check all configured platforms
    for platform in config.get_supported_platforms():
        configs = config.get_platform_configs(platform)
        print(f"Platform {platform} has {len(configs)} configurations")

except FileNotFoundError:
    print("Configuration file not found")
except ConfigError as e:
    print(f"Configuration error: {e}")
```

### Creating Configuration Programmatically

```python
from branch_manager.model import AppConfig, GitHubConfig

# Create GitHub config
gh_config = GitHubConfig(
    organization="my-org",
    included_repo_regex="^test-",
    days_before_branch_stale=15,
    access_token_environment_variable="MY_GITHUB_TOKEN"
)

# Create main config
config = AppConfig(github=[gh_config])

# Use configuration methods
print(f"Supported platforms: {config.get_supported_platforms()}")
print(f"Has any configs: {config.has_any_configs()}")
print(f"Has GitHub configs: {config.has_platform_configs('github')}")

for gh in config.get_github_configs():
    print(f"Managing {gh.organization}")
```

### Error Handling

```python
from branch_manager.model import AppConfig
from pydantic import ValidationError

try:
    config = AppConfig.from_yaml_file("config.yaml")
except ValidationError as e:
    print("Validation errors:")
    for error in e.errors():
        print(f"  {error['loc']}: {error['msg']}")
except ValueError as e:
    print(f"Configuration error: {e}")
```

## Field Aliases

The model supports both Python-style and YAML-style field names:

| Python Field | YAML Alias |
|-------------|------------|
| `included_repo_regex` | `included-repo-regex` |
| `exempt_authors_regex` | `exempt-authors-regex` |
| `exempt_branches_regex` | `exempt-branches-regex` |
| `days_before_branch_stale` | `days-before-branch-stale` |
| `days_before_branch_delete` | `days-before-branch-delete` |
| `access_token_environment_variable` | `access-token-environment-variable` |

This allows natural YAML syntax while maintaining Python naming conventions in code.

## Platform Extensibility

The configuration system is designed to support multiple Git platforms:

- **Current:** GitHub support via `GitHubConfig` (alias for `GitPlatformConfig`)
- **Future:** Additional platforms can be added by extending `GitPlatformConfig`
- **Methods:** Use platform-agnostic methods like `get_platform_configs()` for forward compatibility
