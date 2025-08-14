"""Main module for the branch-manager application."""

import importlib.metadata
import os
from pathlib import Path

import click

from branch_manager.git.base import BaseGitClient
from branch_manager.git.factory import GitClientFactory
from branch_manager.logging import error, info, setup_logger, warn
from branch_manager.model import AppConfig, ConfigError, GitPlatformConfig


def get_access_token(access_token_env_var: str = "ACCESS_TOKEN") -> str | None:
    """Get access token from environment variables.

    Args:
        access_token_env_var: Environment variable name to check (default: "ACCESS_TOKEN")

    Returns:
        Access token if found, None otherwise
    """

    token = os.getenv(access_token_env_var)
    if token:
        return token

    return None


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.version_option(
    version=importlib.metadata.version("branch-manager"), prog_name="branch-manager"
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to YAML config file",
)
@click.option("--dry-run", "-d", is_flag=True, help="Dry run mode")
def main(verbose: bool, config: str | Path, dry_run: bool) -> None:
    """Manages stale branches in your managed Git Hosting platform (ie. GitHub)."""

    # Setup logging first
    setup_logger(verbose=verbose)

    info("🍞 BranchManager 🗑️")
    info("=" * 20)

    if verbose:
        info("Verbose mode enabled")

    if dry_run:
        warn("Dry run mode enabled - no changes will be made")

    try:
        # Load configuration
        info("Loading configuration from: %s", config)
        app_config = AppConfig.from_yaml_file(config)

        # Display configuration summary
        for platform, configs in app_config.get_all_platform_configs().items():
            if configs:  # Only process platforms with configurations
                info(f"Processing {platform} with {len(configs)} organizations")
                for org_config in configs:
                    # Run the main logic - Get access token from environment
                    access_token = get_access_token(org_config.access_token_environment_variable)
                    if not access_token:
                        error("Access token not found")
                        info("Set one of the following environment variables:")
                        info("  • ACCESS_TOKEN (generic)")
                        info("or use access_token_environment_variable in your config to override")
                        info("\nExample:")
                        info("  export ACCESS_TOKEN='your_token_here'")
                        raise click.Abort()

                    info("Access token found, initializing client")

                    try:
                        client = GitClientFactory.create_client(platform, access_token)
                    except ValueError as e:
                        error("%s", e)
                        return None

                    if not client.is_authenticated():
                        error("Authentication failed. Please check your credentials.")
                        return None

                    info("Authentication successful")

                    runner(client, org_config, dry_run)

    except (ConfigError, FileNotFoundError, ValueError) as e:
        error("Configuration Error: %s", e)
        raise click.Abort() from e
    except Exception as e:
        error("Unexpected error: %s", e)
        if verbose:
            import traceback

            traceback.print_exc()
        raise click.Abort() from e


def runner(client: BaseGitClient, org_config: GitPlatformConfig, dry_run: bool) -> None:
    """Main runner function to process organizations and branches."""

    # Process each GitHub organization
    total_summary = {"repos": 0, "deleted": 0, "notified": 0, "skipped": 0, "errors": 0}

    org_results = client.process_organization(
        org_name=org_config.organization, config=org_config, dry_run=dry_run
    )

    # Aggregate results
    for key in total_summary:
        total_summary[key] += org_results[key]

    # Summary
    info("=" * 50)
    info("Processing Summary:")
    info(f"  Repositories processed: {total_summary['repos']}")
    info(f"  Branches deleted: {total_summary['deleted']}")
    info(f"  Notifications sent: {total_summary['notified']}")
    info(f"  Branches skipped: {total_summary['skipped']}")
    if total_summary["errors"] > 0:
        warn(f"  Errors encountered: {total_summary['errors']}")

    info("Closing git client connection")
    client.close()
    return None


if __name__ == "__main__":
    main()
