"""Base API client interface for git hosting providers."""

import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from branch_manager.logging import debug, error, info, warn
from branch_manager.model import GitPlatformConfig


class BranchAction:
    """Represents an action to be taken on a branch."""

    def __init__(
        self,
        action_type: str,
        branch: str,
        repo: str,
        days_old: int,
        commit_data: dict[str, Any],
        reason: str = "",
    ):
        self.action_type = action_type  # 'delete', 'notify', 'skip'
        self.branch = branch
        self.repo = repo
        self.days_old = days_old
        self.commit_data = commit_data
        self.reason = reason

    def __repr__(self) -> str:
        return f"BranchAction({self.action_type}, {self.branch}, {self.days_old} days)"


class BaseGitClient(ABC):
    """Abstract base class for git hosting API clients."""

    def __init__(self, access_token: str) -> None:
        """Initialize the client with an access token.

        Args:
            access_token: API access token for the git hosting service
        """
        self.access_token = access_token

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Check if the client is properly authenticated."""
        pass

    @abstractmethod
    def _list_all_repositories(self, org_name: str) -> list[str]:
        """Internal method to list ALL repositories for a given organization."""
        pass

    @abstractmethod
    def _list_all_branches(self, org_name: str, repo_name: str) -> list[str]:
        """Internal method to list ALL branches in a given repository."""
        pass

    @abstractmethod
    def _get_latest_commit(
        self, org_name: str, repo_name: str, branch_name: str
    ) -> dict[str, Any] | None:
        """Internal method to get latest commit data for a specific branch."""
        pass

    @abstractmethod
    def _delete_branch_impl(self, org_name: str, repo_name: str, branch_name: str) -> None:
        """Internal method to delete a branch."""
        pass

    @abstractmethod
    def _notify_stale_branch_impl(self, message: str, sha: str, repo: str) -> None:
        """Internal method to notify about a stale branch."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Cleanly close API connections."""
        pass

    # Public interface methods with filtering
    def list_repositories(self, org_name: str, include_pattern: str | None = None) -> list[str]:
        """List repositories with optional filtering."""
        all_repos = self._list_all_repositories(org_name)
        if not include_pattern:
            return all_repos
        return self._filter_repositories(all_repos, include_pattern)

    def list_branches(
        self, org_name: str, repo_name: str, exclude_pattern: str | None = None
    ) -> list[str]:
        """List branches with optional filtering."""
        all_branches = self._list_all_branches(org_name, repo_name)
        if not exclude_pattern:
            return all_branches
        return self._filter_branches(all_branches, exclude_pattern)

    def get_latest_commit(
        self, org_name: str, repo_name: str, branch_name: str, exclude_pattern: str | None = None
    ) -> dict[str, Any] | None:
        """Get latest commit with optional author filtering."""
        commit_data = self._get_latest_commit(org_name, repo_name, branch_name)
        if not commit_data or not exclude_pattern:
            return commit_data
        return self._filter_commit(commit_data, exclude_pattern)

    # Core business logic methods
    def analyze_repository_branches(
        self, org_name: str, repo_name: str, config: GitPlatformConfig
    ) -> list[BranchAction]:
        """Analyze all branches in a repository and determine required actions.

        Args:
            org_name: Organization name
            repo_name: Repository name
            config: Configuration with stale/delete thresholds

        Returns:
            List of BranchAction objects representing required actions
        """
        info(f"  Analyzing repository: {repo_name}")

        # Get filtered branches
        branches = self.list_branches(
            org_name=org_name, repo_name=repo_name, exclude_pattern=config.exempt_branches_regex
        )

        if not branches:
            warn(f"No branches found in repository: {repo_name}")
            return []

        info(f"  Found {len(branches)} branches to analyze")
        actions = []

        for branch in branches:
            action = self._analyze_branch(org_name, repo_name, branch, config)
            if action:
                actions.append(action)

        return actions

    def execute_branch_actions(
        self, actions: list[BranchAction], dry_run: bool = False, days_before_delete: int = 30
    ) -> dict[str, int]:
        """Execute a list of branch actions.

        Args:
            actions: List of BranchAction objects to execute
            dry_run: If True, only log what would be done

        Returns:
            Dictionary with counts of each action type executed
        """
        results = {"deleted": 0, "notified": 0, "skipped": 0, "errors": 0}

        for action in actions:
            try:
                if action.action_type == "delete":
                    results["deleted"] += self._execute_delete_action(action, dry_run)
                elif action.action_type == "notify":
                    results["notified"] += self._execute_notify_action(
                        action, dry_run, days_before_delete
                    )
                else:
                    results["skipped"] += 1
                    debug(f"Skipped action for {action.branch}: {action.reason}")

            except Exception as e:
                results["errors"] += 1
                error(f"Failed to execute {action.action_type} on {action.branch}: {e}")

        return results

    def process_organization(
        self, org_name: str, config: GitPlatformConfig, dry_run: bool = False
    ) -> dict[str, int]:
        """Process all repositories in an organization for stale branches.

        Args:
            org_name: Organization name
            config: Configuration for the organization
            dry_run: If True, only log what would be done

        Returns:
            Dictionary with summary statistics
        """
        info(f"Processing organization: {org_name}")

        # Get filtered repositories
        repos = self.list_repositories(
            org_name=org_name, include_pattern=config.included_repo_regex
        )

        if not repos:
            warn(f"No repositories found for organization: {org_name}")
            return {"repos": 0, "deleted": 0, "notified": 0, "skipped": 0, "errors": 0}

        info(f"Found {len(repos)} repositories matching filter")

        total_results = {
            "repos": len(repos),
            "deleted": 0,
            "notified": 0,
            "skipped": 0,
            "errors": 0,
        }

        for repo in repos:
            # Analyze repository
            actions = self.analyze_repository_branches(org_name, repo, config)

            # Execute actions
            repo_results = self.execute_branch_actions(
                actions, dry_run, config.days_before_branch_delete
            )

            # Aggregate results
            for key in ["deleted", "notified", "skipped", "errors"]:
                total_results[key] += repo_results[key]

        return total_results

    # Private helper methods
    def _analyze_branch(
        self, org_name: str, repo_name: str, branch_name: str, config: GitPlatformConfig
    ) -> BranchAction | None:
        """Analyze a single branch and determine the required action."""
        try:
            # Get latest commit
            commit_data = self.get_latest_commit(
                org_name=org_name,
                repo_name=repo_name,
                branch_name=branch_name,
                exclude_pattern=config.exempt_authors_regex,
            )

            if not commit_data:
                return BranchAction(
                    "skip",
                    branch_name,
                    f"{org_name}/{repo_name}",
                    0,
                    {},
                    "No commit data or exempt author",
                )

            # Parse commit date
            commit_date_str = commit_data.get("date", "")
            if not commit_date_str:
                warn(f"No commit date found for branch {branch_name}")
                return None

            commit_datetime = datetime.fromisoformat(commit_date_str.replace("Z", "+00:00"))
            current_time = datetime.now(commit_datetime.tzinfo)
            days_since_commit = (current_time - commit_datetime).days

            # Add metadata to commit data
            commit_data["repo"] = f"{org_name}/{repo_name}"
            commit_data["branch"] = branch_name

            debug(f"Branch {branch_name}: {days_since_commit} days since last commit")

            # Determine action based on age
            if days_since_commit >= config.days_before_branch_delete:
                return BranchAction(
                    "delete",
                    branch_name,
                    f"{org_name}/{repo_name}",
                    days_since_commit,
                    commit_data,
                    f"""Branch is {days_since_commit} days old
                    (>= {config.days_before_branch_delete})""",
                )

            elif days_since_commit >= config.days_before_branch_stale:
                return BranchAction(
                    "notify",
                    branch_name,
                    f"{org_name}/{repo_name}",
                    days_since_commit,
                    commit_data,
                    f"""Branch is {days_since_commit} days old
                    (>= {config.days_before_branch_stale})""",
                )
            else:
                return BranchAction(
                    "skip",
                    branch_name,
                    f"{org_name}/{repo_name}",
                    days_since_commit,
                    commit_data,
                    f"Branch is only {days_since_commit} days old",
                )

        except ValueError as e:
            error(f"Error parsing commit date for branch {branch_name}: {e}")
            return None
        except Exception as e:
            error(f"Unexpected error analyzing branch {branch_name}: {e}")
            return None

    def _execute_delete_action(self, action: BranchAction, dry_run: bool) -> int:
        """Execute a delete action."""
        warn(f"Branch {action.branch} is ready for deletion ({action.days_old} days old)")

        if dry_run:
            warn(f"  [DRY RUN] Would delete branch: {action.branch}")
            return 1
        else:
            org_name, repo_name = action.repo.split("/", 1)
            self._delete_branch_impl(org_name, repo_name, action.branch)
            info(f"  Deleted stale branch: {action.branch}")
            return 1

    def _execute_notify_action(
        self, action: BranchAction, dry_run: bool, days_before_delete: int
    ) -> int:
        """Execute a notify action."""
        info(f"Branch {action.branch} is stale ({action.days_old} days old)")

        if dry_run:
            warn(f"  [DRY RUN] Would mark branch as stale: {action.branch}")
            return 1
        else:
            author = action.commit_data.get("author", "unknown")
            sha = action.commit_data.get("sha", "")

            days_until_delete = max(days_before_delete - action.days_old, 0)
            msg = (
                f"[STALE BRANCH] @{author} - Branch '{action.branch}' has not been "
                f"updated in {action.days_old} days. "
                f"Please review its validity (push a new commit to reset) or it will be deleted in "
                f"{days_until_delete} days."
            )

            self._notify_stale_branch_impl(message=msg, sha=sha, repo=action.repo)
            info(f"  Notified user about stale branch: {action.branch}")
            return 1

    # Filter helper methods (same as before)
    def _filter_repositories(self, repos: list[str], include_pattern: str) -> list[str]:
        """Filter repositories by include pattern."""
        try:
            pattern = re.compile(include_pattern)
            filtered = [repo for repo in repos if pattern.search(repo)]
            debug(
                f"""Include filter '{include_pattern}' matched
                {len(filtered)} of {len(repos)} repositories
                """
            )
            return filtered
        except re.error as e:
            error(f"Invalid include regex pattern '{include_pattern}': {e}")
            return []

    def _filter_branches(self, branches: list[str], exclude_pattern: str) -> list[str]:
        """Filter branches by exclude pattern."""
        try:
            pattern = re.compile(exclude_pattern)
            filtered = [branch for branch in branches if not pattern.search(branch)]
            debug(
                f"""Exclude filter '{exclude_pattern}' removed
                {len(branches) - len(filtered)} branches
                """
            )
            return filtered
        except re.error as e:
            error(f"Invalid exclude regex pattern '{exclude_pattern}': {e}")
            return branches

    def _filter_commit(
        self, commit_data: dict[str, Any], exclude_pattern: str
    ) -> dict[str, Any] | None:
        """Filter commit by author pattern."""
        try:
            pattern = re.compile(exclude_pattern)
            author = commit_data.get("author", "")
            if pattern.search(author):
                debug(f"Exempted commit by author: {author}")
                return None
            return commit_data
        except re.error as e:
            error(f"Invalid author exclude regex pattern '{exclude_pattern}': {e}")
            return commit_data
