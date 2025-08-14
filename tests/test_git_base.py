"""Tests for the BaseGitClient and BranchAction classes."""

from datetime import UTC, datetime
from unittest.mock import patch

from branch_manager.git.base import BaseGitClient, BranchAction
from branch_manager.model import GitHubConfig


class MockGitClient(BaseGitClient):
    """Mock implementation of BaseGitClient for testing."""

    def __init__(self, access_token: str):
        super().__init__(access_token)
        self.authenticated = True
        self.repos = []
        self.branches = {}
        self.commits = {}
        self.deleted_branches = []
        self.notifications = []
        self.closed = False

    def is_authenticated(self) -> bool:
        return self.authenticated

    def _list_all_repositories(self, org_name: str) -> list[str]:
        return self.repos

    def _list_all_branches(self, org_name: str, repo_name: str) -> list[str]:
        return self.branches.get(f"{org_name}/{repo_name}", [])

    def _get_latest_commit(self, org_name: str, repo_name: str, branch_name: str) -> dict:
        key = f"{org_name}/{repo_name}/{branch_name}"
        return self.commits.get(key)

    def _delete_branch_impl(self, org_name: str, repo_name: str, branch_name: str) -> None:
        self.deleted_branches.append(f"{org_name}/{repo_name}/{branch_name}")

    def _notify_stale_branch_impl(self, message: str, sha: str, repo: str) -> None:
        self.notifications.append({"message": message, "sha": sha, "repo": repo})

    def close(self) -> None:
        self.closed = True


class TestBranchAction:
    """Test cases for BranchAction class."""

    def test_branch_action_creation(self):
        """Test creating a BranchAction instance."""
        commit_data = {"sha": "abc123", "author": "test", "date": "2023-01-01T00:00:00Z"}
        action = BranchAction(
            action_type="delete",
            branch="feature-branch",
            repo="org/repo",
            days_old=30,
            commit_data=commit_data,
            reason="Too old",
        )

        assert action.action_type == "delete"
        assert action.branch == "feature-branch"
        assert action.repo == "org/repo"
        assert action.days_old == 30
        assert action.commit_data == commit_data
        assert action.reason == "Too old"

    def test_branch_action_repr(self):
        """Test BranchAction string representation."""
        action = BranchAction("notify", "test-branch", "org/repo", 15, {})
        repr_str = repr(action)

        assert "BranchAction" in repr_str
        assert "notify" in repr_str
        assert "test-branch" in repr_str
        assert "15 days" in repr_str

    def test_branch_action_default_reason(self):
        """Test BranchAction with default empty reason."""
        action = BranchAction("skip", "branch", "repo", 5, {})
        assert action.reason == ""


class TestBaseGitClient:
    """Test cases for BaseGitClient base class and concrete implementations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = MockGitClient("test_token")
        self.config = GitHubConfig(
            organization="test-org",
            included_repo_regex=".*",
            exempt_branches_regex="main|master|develop",
            exempt_authors_regex="bot|automation",
            days_before_branch_stale=7,
            days_before_branch_delete=30,
        )

    def test_client_initialization(self):
        """Test client initialization."""
        assert self.client.access_token == "test_token"
        assert self.client.is_authenticated()

    def test_list_repositories_no_filter(self):
        """Test listing repositories without filtering."""
        self.client.repos = ["repo1", "repo2", "repo3"]

        repos = self.client.list_repositories("test-org")
        assert repos == ["repo1", "repo2", "repo3"]

    def test_list_repositories_with_filter(self):
        """Test listing repositories with include pattern."""
        self.client.repos = ["web-app", "mobile-app", "docs", "test-suite"]

        repos = self.client.list_repositories("test-org", include_pattern=".*app.*")
        assert repos == ["web-app", "mobile-app"]

    def test_list_branches_no_filter(self):
        """Test listing branches without filtering."""
        self.client.branches["test-org/repo1"] = ["main", "feature1", "feature2"]

        branches = self.client.list_branches("test-org", "repo1")
        assert branches == ["main", "feature1", "feature2"]

    def test_list_branches_with_filter(self):
        """Test listing branches with exclude pattern."""
        self.client.branches["test-org/repo1"] = ["main", "develop", "feature1", "hotfix"]

        branches = self.client.list_branches("test-org", "repo1", exclude_pattern="main|develop")
        assert branches == ["feature1", "hotfix"]

    def test_get_latest_commit_no_filter(self):
        """Test getting latest commit without filtering."""
        commit_data = {"sha": "abc123", "author": "user", "date": "2023-01-01T00:00:00Z"}
        self.client.commits["test-org/repo1/branch1"] = commit_data

        result = self.client.get_latest_commit("test-org", "repo1", "branch1")
        assert result == commit_data

    def test_get_latest_commit_with_author_filter_excluded(self):
        """Test getting latest commit with author filtering - excluded author."""
        commit_data = {"sha": "abc123", "author": "automation-bot", "date": "2023-01-01T00:00:00Z"}
        self.client.commits["test-org/repo1/branch1"] = commit_data

        result = self.client.get_latest_commit(
            "test-org", "repo1", "branch1", exclude_pattern="bot"
        )
        assert result is None

    def test_get_latest_commit_with_author_filter_included(self):
        """Test getting latest commit with author filtering - included author."""
        commit_data = {"sha": "abc123", "author": "human-user", "date": "2023-01-01T00:00:00Z"}
        self.client.commits["test-org/repo1/branch1"] = commit_data

        result = self.client.get_latest_commit(
            "test-org", "repo1", "branch1", exclude_pattern="bot"
        )
        assert result == commit_data

    def test_filter_repositories_valid_regex(self):
        """Test repository filtering with valid regex."""
        repos = ["frontend-app", "backend-api", "mobile-app", "docs"]
        filtered = self.client._filter_repositories(repos, ".*app.*")
        assert filtered == ["frontend-app", "mobile-app"]

    def test_filter_repositories_invalid_regex(self):
        """Test repository filtering with invalid regex."""
        repos = ["repo1", "repo2"]
        with patch("branch_manager.git.base.error") as mock_error:
            filtered = self.client._filter_repositories(repos, "[invalid")
            assert filtered == []
            mock_error.assert_called_once()

    def test_filter_branches_valid_regex(self):
        """Test branch filtering with valid regex."""
        branches = ["main", "develop", "feature1", "feature2"]
        filtered = self.client._filter_branches(branches, "main|develop")
        assert filtered == ["feature1", "feature2"]

    def test_filter_branches_invalid_regex(self):
        """Test branch filtering with invalid regex."""
        branches = ["branch1", "branch2"]
        with patch("branch_manager.git.base.error") as mock_error:
            filtered = self.client._filter_branches(branches, "[invalid")
            assert filtered == branches  # Should return original list on error
            mock_error.assert_called_once()

    def test_filter_commit_excluded_author(self):
        """Test commit filtering - excluded author."""
        commit_data = {"author": "automation-bot", "sha": "abc123"}
        result = self.client._filter_commit(commit_data, "bot")
        assert result is None

    def test_filter_commit_included_author(self):
        """Test commit filtering - included author."""
        commit_data = {"author": "human-user", "sha": "abc123"}
        result = self.client._filter_commit(commit_data, "bot")
        assert result == commit_data

    def test_filter_commit_invalid_regex(self):
        """Test commit filtering with invalid regex."""
        commit_data = {"author": "user", "sha": "abc123"}
        with patch("branch_manager.git.base.error") as mock_error:
            result = self.client._filter_commit(commit_data, "[invalid")
            assert result == commit_data
            mock_error.assert_called_once()

    def test_analyze_branch_delete_action(self):
        """Test branch analysis - should delete old branch."""
        # Set up old commit (45 days old)
        commit_date = datetime(2023, 1, 1, tzinfo=UTC)
        commit_data = {"author": "user", "date": commit_date.isoformat(), "sha": "abc123"}
        self.client.commits["test-org/repo1/old-branch"] = commit_data

        # Mock datetime.now to return a specific time
        current_time = datetime(2023, 2, 15, tzinfo=UTC)
        with patch("branch_manager.git.base.datetime") as mock_datetime:
            mock_datetime.now.return_value = current_time
            mock_datetime.fromisoformat = datetime.fromisoformat

            action = self.client._analyze_branch("test-org", "repo1", "old-branch", self.config)

            assert action is not None
            assert action.action_type == "delete"
            assert action.branch == "old-branch"
            assert action.repo == "test-org/repo1"
            assert action.days_old == 45
            assert "repo" in action.commit_data
            assert "branch" in action.commit_data

    def test_analyze_branch_notify_action(self):
        """Test branch analysis - should notify for stale branch."""
        # Set up stale commit (15 days old)
        commit_date = datetime(2023, 1, 5, tzinfo=UTC)
        commit_data = {"author": "user", "date": commit_date.isoformat(), "sha": "abc123"}
        self.client.commits["test-org/repo1/stale-branch"] = commit_data

        # Mock datetime.now to return a specific time
        current_time = datetime(2023, 1, 20, tzinfo=UTC)
        with patch("branch_manager.git.base.datetime") as mock_datetime:
            mock_datetime.now.return_value = current_time
            mock_datetime.fromisoformat = datetime.fromisoformat

            action = self.client._analyze_branch("test-org", "repo1", "stale-branch", self.config)

            assert action is not None
            assert action.action_type == "notify"
            assert action.branch == "stale-branch"
            assert action.days_old == 15

    def test_analyze_branch_skip_action(self):
        """Test branch analysis - should skip fresh branch."""
        # Set up fresh commit (3 days old)
        commit_date = datetime(2023, 1, 7, tzinfo=UTC)
        commit_data = {"author": "user", "date": commit_date.isoformat(), "sha": "abc123"}
        self.client.commits["test-org/repo1/fresh-branch"] = commit_data

        # Mock datetime.now to return a specific time
        current_time = datetime(2023, 1, 10, tzinfo=UTC)
        with patch("branch_manager.git.base.datetime") as mock_datetime:
            mock_datetime.now.return_value = current_time
            mock_datetime.fromisoformat = datetime.fromisoformat

            action = self.client._analyze_branch("test-org", "repo1", "fresh-branch", self.config)

            assert action is not None
            assert action.action_type == "skip"
            assert action.days_old == 3

    def test_analyze_branch_no_commit_data(self):
        """Test branch analysis with no commit data."""
        # No commit data set up
        action = self.client._analyze_branch("test-org", "repo1", "branch", self.config)

        assert action is not None
        assert action.action_type == "skip"
        assert action.reason == "No commit data or exempt author"

    def test_analyze_branch_invalid_date_format(self):
        """Test branch analysis with invalid date format."""
        commit_data = {"author": "user", "date": "invalid-date", "sha": "abc123"}
        self.client.commits["test-org/repo1/branch"] = commit_data

        with patch("branch_manager.git.base.error") as mock_error:
            action = self.client._analyze_branch("test-org", "repo1", "branch", self.config)
            assert action is None
            mock_error.assert_called_once()

    def test_analyze_branch_no_date_field(self):
        """Test branch analysis with missing date field."""
        commit_data = {
            "author": "user",
            "sha": "abc123",
            # Missing date field
        }
        self.client.commits["test-org/repo1/branch"] = commit_data

        with patch("branch_manager.git.base.warn") as mock_warn:
            action = self.client._analyze_branch("test-org", "repo1", "branch", self.config)
            assert action is None
            mock_warn.assert_called_once()

    def test_analyze_repository_branches(self):
        """Test analyzing all branches in a repository."""
        # Set up test data - note we need to include branches that will be filtered
        self.client.branches["test-org/repo1"] = ["feature1", "feature2"]

        # Mock the branch analysis
        with patch.object(self.client, "_analyze_branch") as mock_analyze:
            mock_analyze.side_effect = [
                BranchAction("notify", "feature1", "test-org/repo1", 10, {}, "stale"),
                BranchAction("delete", "feature2", "test-org/repo1", 35, {}, "old"),
            ]

            actions = self.client.analyze_repository_branches("test-org", "repo1", self.config)

            # Both actions should be returned since neither is None
            assert len(actions) == 2
            assert actions[0].action_type == "notify"
            assert actions[1].action_type == "delete"

    def test_analyze_repository_branches_filters_none_actions(self):
        """Test that None actions are filtered out."""
        # Set up test data
        self.client.branches["test-org/repo1"] = ["branch1", "branch2", "branch3"]

        # Mock the branch analysis to return mix of None and valid actions
        with patch.object(self.client, "_analyze_branch") as mock_analyze:
            mock_analyze.side_effect = [
                None,  # First branch analysis returns None
                BranchAction("notify", "branch2", "test-org/repo1", 10, {}, "stale"),
                None,  # Third branch analysis returns None
            ]

            actions = self.client.analyze_repository_branches("test-org", "repo1", self.config)

            # Only 1 action should be returned (None values are filtered out)
            assert len(actions) == 1
            assert actions[0].action_type == "notify"
            assert actions[0].branch == "branch2"

    def test_analyze_repository_branches_no_branches(self):
        """Test analyzing repository with no branches."""
        self.client.branches["test-org/empty-repo"] = []

        actions = self.client.analyze_repository_branches("test-org", "empty-repo", self.config)
        assert actions == []

    def test_execute_branch_actions(self):
        """Test executing a list of branch actions."""
        actions = [
            BranchAction("delete", "old-branch", "test-org/repo1", 35, {"sha": "abc"}, "old"),
            BranchAction("notify", "stale-branch", "test-org/repo1", 15, {"sha": "def"}, "stale"),
            BranchAction("skip", "fresh-branch", "test-org/repo1", 3, {"sha": "ghi"}, "fresh"),
        ]

        results = self.client.execute_branch_actions(actions, dry_run=False)

        assert results["deleted"] == 1
        assert results["notified"] == 1
        assert results["skipped"] == 1
        assert results["errors"] == 0

        # Verify actions were executed
        assert "test-org/repo1/old-branch" in self.client.deleted_branches
        assert len(self.client.notifications) == 1

    def test_execute_branch_actions_dry_run(self):
        """Test executing branch actions in dry run mode."""
        actions = [
            BranchAction("delete", "old-branch", "test-org/repo1", 35, {"sha": "abc"}, "old"),
            BranchAction("notify", "stale-branch", "test-org/repo1", 15, {"sha": "def"}, "stale"),
        ]

        results = self.client.execute_branch_actions(actions, dry_run=True)

        assert results["deleted"] == 1
        assert results["notified"] == 1
        assert results["errors"] == 0

        # Verify no actual actions were executed
        assert len(self.client.deleted_branches) == 0
        assert len(self.client.notifications) == 0

    def test_execute_branch_actions_with_errors(self):
        """Test executing branch actions with errors."""

        # Mock the delete implementation to raise an exception
        def failing_delete(org_name, repo_name, branch_name):
            raise Exception("Delete failed")

        self.client._delete_branch_impl = failing_delete

        actions = [
            BranchAction(
                "delete", "problematic-branch", "test-org/repo1", 35, {"sha": "abc"}, "old"
            )
        ]

        with patch("branch_manager.git.base.error") as mock_error:
            results = self.client.execute_branch_actions(actions, dry_run=False)

            assert results["deleted"] == 0
            assert results["errors"] == 1
            mock_error.assert_called_once()

    def test_process_organization(self):
        """Test processing an entire organization."""
        # Set up test data
        self.client.repos = ["repo1", "repo2"]

        # Mock repository analysis
        mock_actions = [
            BranchAction("delete", "old-branch", "test-org/repo1", 35, {"sha": "abc"}, "old"),
            BranchAction("notify", "stale-branch", "test-org/repo1", 15, {"sha": "def"}, "stale"),
        ]

        with patch.object(self.client, "analyze_repository_branches") as mock_analyze:
            with patch.object(self.client, "execute_branch_actions") as mock_execute:
                mock_analyze.return_value = mock_actions
                mock_execute.return_value = {"deleted": 1, "notified": 1, "skipped": 0, "errors": 0}

                results = self.client.process_organization("test-org", self.config, dry_run=False)

                assert results["repos"] == 2
                assert results["deleted"] == 2  # 1 per repo * 2 repos
                assert results["notified"] == 2
                assert mock_analyze.call_count == 2
                assert mock_execute.call_count == 2

    def test_process_organization_no_repos(self):
        """Test processing organization with no repositories."""
        self.client.repos = []

        results = self.client.process_organization("test-org", self.config)

        assert results["repos"] == 0
        assert results["deleted"] == 0
        assert results["notified"] == 0
        assert results["skipped"] == 0
        assert results["errors"] == 0

    def test_execute_delete_action_implementation(self):
        """Test the delete action execution implementation."""
        action = BranchAction("delete", "test-branch", "test-org/repo1", 35, {"sha": "abc"}, "old")

        result = self.client._execute_delete_action(action, dry_run=False)
        assert result == 1
        assert "test-org/repo1/test-branch" in self.client.deleted_branches

    def test_execute_notify_action_implementation(self):
        """Test the notify action execution implementation."""
        commit_data = {"author": "testuser", "sha": "abc123"}
        action = BranchAction("notify", "test-branch", "test-org/repo1", 15, commit_data, "stale")

        result = self.client._execute_notify_action(action, dry_run=False, days_before_delete=30)
        assert result == 1
        assert len(self.client.notifications) == 1

        notification = self.client.notifications[0]
        assert "testuser" in notification["message"]
        assert "test-branch" in notification["message"]
        assert notification["sha"] == "abc123"
        assert notification["repo"] == "test-org/repo1"
