"""GitHub API client implementation."""

from typing import Any

from github import Auth, Github, GithubException

from branch_manager.git.base import BaseGitClient
from branch_manager.logging import debug, error, info, warn


class GitHubClient(BaseGitClient):
    """GitHub API client for managing repositories and branches."""

    def __init__(self, access_token: str) -> None:
        """Initialize GitHub client with access token.

        Args:
            access_token: GitHub personal access token or fine-grained token
        """
        super().__init__(access_token)
        self.auth = Auth.Token(access_token)
        self.client = Github(auth=self.auth)
        self.org_name = None

    def is_authenticated(self) -> bool:
        """Check if the client is properly authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        try:
            user = self.client.get_user()
            info(f"Authenticated as: {user.login}")
            return True
        except GithubException as e:
            error(f"GitHub authentication failed: {e}")
            return False
        except Exception as e:
            error(f"Unexpected authentication error: {e}")
            return False

    def _list_all_repositories(self, org_name: str) -> list[str]:
        """List all repositories for a given organization.

        Args:
            org_name: GitHub organization name

        Returns:
            List of repository names, ignores archived and disabled repositories
        """
        info(f"Fetching repositories for organization: {org_name}")

        try:
            # Get organization
            try:
                org = self.client.get_organization(org_name)
            except GithubException as e:
                if e.status == 404:
                    error(f"Organization '{org_name}' not found")
                elif e.status == 403:
                    error(f"Access denied to organization '{org_name}' - check permissions")
                else:
                    error(f"Failed to access organization '{org_name}': {e}")
                return []

            # Get repositories
            repos = org.get_repos()
            total_repos = 0
            filtered_repos = []

            for repo in repos:
                total_repos += 1

                # Skip archived and disabled repos
                if repo.archived:
                    debug(f"Skipping archived repo: {repo.name}")
                    continue

                if repo.disabled:
                    debug(f"Skipping disabled repo: {repo.name}")
                    continue

                filtered_repos.append(repo.name)

            info(f"Found {total_repos} total repositories")

            return filtered_repos

        except GithubException as e:
            error(f"GitHub API error while listing repositories: {e}")
            return []
        except Exception as e:
            error(f"Unexpected error while listing repositories: {e}")
            return []

    def _list_all_branches(self, org_name: str, repo_name: str) -> list[str]:
        """List all branches in a given repository.

        Args:
            org_name: GitHub organization name
            repo_name: Repository name

        Returns:
            List of branch names
        """
        full_repo_name = f"{org_name}/{repo_name}"
        info(f"Fetching branches for repository: {full_repo_name}")

        try:
            repo = self.client.get_repo(full_repo_name)
            branches = repo.get_branches()
            branch_names = [branch.name for branch in branches]

            info(f"Found {len(branch_names)} branches in {full_repo_name}")
            return branch_names

        except GithubException as e:
            if e.status == 404:
                error(f"Repository '{full_repo_name}' not found")
            elif e.status == 403:
                error(f"Access denied to repository '{full_repo_name}'")
            else:
                error(f"GitHub API error for repository '{full_repo_name}': {e}")
            return []
        except Exception as e:
            error(f"Unexpected error while listing branches for '{full_repo_name}': {e}")
            return []

    def _get_latest_commit(
        self, org_name: str, repo_name: str, branch_name: str
    ) -> dict[str, Any] | None:
        """Get latest commit data for a specific branch in a repository.

        Args:
            org_name: GitHub organization name
            repo_name: Repository name
            branch_name: Branch name

        Returns:
            Dictionary with commit data or None if not found
        """
        full_repo_name = f"{org_name}/{repo_name}"
        info(f"Fetching latest commit data for {full_repo_name} on branch '{branch_name}'")

        try:
            repo = self.client.get_repo(full_repo_name)
            branch = repo.get_branch(branch_name)
            commit_data = {
                "repo": full_repo_name,
                "branch": branch_name,
                "sha": branch.commit.sha,
                "message": branch.commit.commit.message,
                "author": branch.commit.author.login,
                "date": branch.commit.commit.author.date.isoformat(),
            }

            debug(f"Latest commit on {full_repo_name} ({branch_name}): {commit_data['sha']}")
            return commit_data

        except GithubException as e:
            if e.status == 404:
                error(f"Branch '{branch_name}' not found in repository '{full_repo_name}'")
            elif e.status == 403:
                error(f"Access denied to branch '{branch_name}' in repository '{full_repo_name}'")
            else:
                error(f"GitHub API error for {full_repo_name} on branch '{branch_name}': {e}")
            return None
        except Exception as e:
            error(
                f"""
                Unexpected error while fetching latest commit data for
                {full_repo_name} on branch '{branch_name}': {e}
                """
            )
            return None

    def create_commit_msg(self, message: str, sha: str, repo: str) -> None:
        """Notify end user about a specific commit."""
        info(f"{message} (SHA: {sha})")
        try:
            info(f"Notification sent for commit {sha}: {message}")
            repo_obj = self.client.get_repo(repo)
            repo_obj.get_commit(sha).create_comment(body=message)
        except Exception as e:
            warn(f"Failed to send notification for commit {sha}: {e}")

    def _delete_branch_impl(self, org_name: str, repo_name: str, branch_name: str) -> None:
        """Internal method to delete a branch."""
        full_repo_name = f"{org_name}/{repo_name}"
        repo = self.client.get_repo(full_repo_name)
        ref = f"heads/{branch_name}"
        repo.get_git_ref(ref).delete()

    def _notify_stale_branch_impl(self, message: str, sha: str, repo: str) -> None:
        """Internal method to notify about a stale branch."""
        repo_obj = self.client.get_repo(repo)
        repo_obj.get_commit(sha).create_comment(body=message)

    def close(self) -> None:
        """Cleanly close API connections."""
        if self.client:
            try:
                self.client.close()
                info("GitHub client connection closed")
            except Exception as e:
                warn(f"Error closing GitHub client: {e}")
