"""Tests for the GitHubClient implementation."""

from unittest.mock import Mock, patch

from github import GithubException

from branch_manager.git.github.main import GitHubClient


class TestGitHubClient:
    """Test cases for GitHubClient."""

    def setup_method(self):
        """Set up test fixtures."""
        self.access_token = "test_token"
        with patch("branch_manager.git.github.main.Github"):
            self.client = GitHubClient(self.access_token)

    def test_client_initialization(self):
        """Test GitHubClient initialization."""
        with patch("branch_manager.git.github.main.Github") as mock_github:
            with patch("branch_manager.git.github.main.Auth") as mock_auth:
                client = GitHubClient("test_token")

                assert client.access_token == "test_token"
                mock_auth.Token.assert_called_once_with("test_token")
                mock_github.assert_called_once()

    def test_is_authenticated_success(self):
        """Test successful authentication check."""
        mock_user = Mock()
        mock_user.login = "testuser"
        self.client.client.get_user.return_value = mock_user

        with patch("branch_manager.git.github.main.info") as mock_info:
            result = self.client.is_authenticated()

            assert result is True
            mock_info.assert_called_with("Authenticated as: testuser")

    def test_is_authenticated_github_exception(self):
        """Test authentication check with GitHub exception."""
        self.client.client.get_user.side_effect = GithubException(401, "Unauthorized", {})

        with patch("branch_manager.git.github.main.error") as mock_error:
            result = self.client.is_authenticated()

            assert result is False
            mock_error.assert_called_once()

    def test_is_authenticated_unexpected_exception(self):
        """Test authentication check with unexpected exception."""
        self.client.client.get_user.side_effect = Exception("Network error")

        with patch("branch_manager.git.github.main.error") as mock_error:
            result = self.client.is_authenticated()

            assert result is False
            mock_error.assert_called_once()

    def test_list_all_repositories_success(self):
        """Test successful repository listing."""
        # Mock organization
        mock_org = Mock()
        self.client.client.get_organization.return_value = mock_org

        # Mock repositories
        mock_repo1 = Mock()
        mock_repo1.name = "repo1"
        mock_repo1.archived = False
        mock_repo1.disabled = False

        mock_repo2 = Mock()
        mock_repo2.name = "repo2"
        mock_repo2.archived = True  # This should be skipped
        mock_repo2.disabled = False

        mock_repo3 = Mock()
        mock_repo3.name = "repo3"
        mock_repo3.archived = False
        mock_repo3.disabled = True  # This should be skipped

        mock_repo4 = Mock()
        mock_repo4.name = "repo4"
        mock_repo4.archived = False
        mock_repo4.disabled = False

        mock_org.get_repos.return_value = [mock_repo1, mock_repo2, mock_repo3, mock_repo4]

        with patch("branch_manager.git.github.main.info") as mock_info:
            with patch("branch_manager.git.github.main.debug") as mock_debug:
                repos = self.client._list_all_repositories("test-org")

                assert repos == ["repo1", "repo4"]
                assert mock_info.call_count >= 2  # Should log fetching and found messages
                assert mock_debug.call_count == 2  # Should log skipped repos

    def test_list_all_repositories_org_not_found(self):
        """Test repository listing with organization not found."""
        self.client.client.get_organization.side_effect = GithubException(404, "Not Found", {})

        with patch("branch_manager.git.github.main.error") as mock_error:
            repos = self.client._list_all_repositories("nonexistent-org")

            assert repos == []
            mock_error.assert_called_once()
            assert "not found" in mock_error.call_args[0][0].lower()

    def test_list_all_repositories_access_denied(self):
        """Test repository listing with access denied."""
        self.client.client.get_organization.side_effect = GithubException(403, "Forbidden", {})

        with patch("branch_manager.git.github.main.error") as mock_error:
            repos = self.client._list_all_repositories("restricted-org")

            assert repos == []
            mock_error.assert_called_once()
            assert "access denied" in mock_error.call_args[0][0].lower()

    def test_list_all_repositories_other_github_exception(self):
        """Test repository listing with other GitHub exception."""
        self.client.client.get_organization.side_effect = GithubException(500, "Server Error", {})

        with patch("branch_manager.git.github.main.error") as mock_error:
            repos = self.client._list_all_repositories("test-org")

            assert repos == []
            mock_error.assert_called_once()

    def test_list_all_repositories_unexpected_exception(self):
        """Test repository listing with unexpected exception."""
        self.client.client.get_organization.side_effect = Exception("Network timeout")

        with patch("branch_manager.git.github.main.error") as mock_error:
            repos = self.client._list_all_repositories("test-org")

            assert repos == []
            mock_error.assert_called_once()

    def test_list_all_branches_success(self):
        """Test successful branch listing."""
        # Mock repository
        mock_repo = Mock()
        self.client.client.get_repo.return_value = mock_repo

        # Mock branches
        mock_branch1 = Mock()
        mock_branch1.name = "main"
        mock_branch2 = Mock()
        mock_branch2.name = "feature1"
        mock_branch3 = Mock()
        mock_branch3.name = "feature2"

        mock_repo.get_branches.return_value = [mock_branch1, mock_branch2, mock_branch3]

        with patch("branch_manager.git.github.main.info") as mock_info:
            branches = self.client._list_all_branches("test-org", "test-repo")

            assert branches == ["main", "feature1", "feature2"]
            assert mock_info.call_count == 2  # Fetching and found messages

    def test_list_all_branches_repo_not_found(self):
        """Test branch listing with repository not found."""
        self.client.client.get_repo.side_effect = GithubException(404, "Not Found", {})

        with patch("branch_manager.git.github.main.error") as mock_error:
            branches = self.client._list_all_branches("test-org", "nonexistent-repo")

            assert branches == []
            mock_error.assert_called_once()
            assert "not found" in mock_error.call_args[0][0].lower()

    def test_list_all_branches_access_denied(self):
        """Test branch listing with access denied."""
        self.client.client.get_repo.side_effect = GithubException(403, "Forbidden", {})

        with patch("branch_manager.git.github.main.error") as mock_error:
            branches = self.client._list_all_branches("test-org", "restricted-repo")

            assert branches == []
            mock_error.assert_called_once()
            assert "access denied" in mock_error.call_args[0][0].lower()

    def test_list_all_branches_other_exception(self):
        """Test branch listing with other exceptions."""
        self.client.client.get_repo.side_effect = Exception("Network error")

        with patch("branch_manager.git.github.main.error") as mock_error:
            branches = self.client._list_all_branches("test-org", "test-repo")

            assert branches == []
            mock_error.assert_called_once()

    def test_get_latest_commit_success(self):
        """Test successful latest commit retrieval."""
        # Mock repository and branch
        mock_repo = Mock()
        mock_branch = Mock()

        # Mock commit data
        mock_commit = Mock()
        mock_commit.sha = "abc123"
        mock_commit.commit.message = "Test commit"
        mock_commit.commit.author.name = "testuser"
        mock_commit.commit.author.date = Mock()
        mock_commit.commit.author.date.isoformat.return_value = "2023-01-01T12:00:00Z"
        mock_commit.author.login = "testuser"

        mock_branch.commit = mock_commit
        mock_repo.get_branch.return_value = mock_branch
        self.client.client.get_repo.return_value = mock_repo

        with patch("branch_manager.git.github.main.info") as mock_info:
            with patch("branch_manager.git.github.main.debug") as mock_debug:
                commit_data = self.client._get_latest_commit("test-org", "test-repo", "test-branch")

                expected = {
                    "repo": "test-org/test-repo",
                    "branch": "test-branch",
                    "sha": "abc123",
                    "message": "Test commit",
                    "author": "testuser",
                    "date": "2023-01-01T12:00:00Z",
                }

                assert commit_data == expected
                mock_info.assert_called_once()
                mock_debug.assert_called_once()

    def test_get_latest_commit_branch_not_found(self):
        """Test latest commit retrieval with branch not found."""
        self.client.client.get_repo.side_effect = GithubException(404, "Not Found", {})

        with patch("branch_manager.git.github.main.error") as mock_error:
            commit_data = self.client._get_latest_commit(
                "test-org", "test-repo", "nonexistent-branch"
            )

            assert commit_data is None
            mock_error.assert_called_once()

    def test_get_latest_commit_access_denied(self):
        """Test latest commit retrieval with access denied."""
        mock_repo = Mock()
        mock_repo.get_branch.side_effect = GithubException(403, "Forbidden", {})
        self.client.client.get_repo.return_value = mock_repo

        with patch("branch_manager.git.github.main.error") as mock_error:
            commit_data = self.client._get_latest_commit(
                "test-org", "test-repo", "restricted-branch"
            )

            assert commit_data is None
            mock_error.assert_called_once()

    def test_get_latest_commit_unexpected_exception(self):
        """Test latest commit retrieval with unexpected exception."""
        self.client.client.get_repo.side_effect = Exception("Network timeout")

        with patch("branch_manager.git.github.main.error") as mock_error:
            commit_data = self.client._get_latest_commit("test-org", "test-repo", "test-branch")

            assert commit_data is None
            mock_error.assert_called_once()

    def test_create_commit_msg_success(self):
        """Test successful commit message creation."""
        mock_repo = Mock()
        mock_commit = Mock()

        self.client.client.get_repo.return_value = mock_repo
        mock_repo.get_commit.return_value = mock_commit

        with patch("branch_manager.git.github.main.info") as mock_info:
            self.client.create_commit_msg("Test message", "abc123", "test-org/test-repo")

            mock_repo.get_commit.assert_called_once_with("abc123")
            mock_commit.create_comment.assert_called_once_with(body="Test message")
            assert mock_info.call_count == 2

    def test_create_commit_msg_failure(self):
        """Test commit message creation failure."""
        self.client.client.get_repo.side_effect = Exception("API error")

        with patch("branch_manager.git.github.main.info"):
            with patch("branch_manager.git.github.main.warn") as mock_warn:
                self.client.create_commit_msg("Test message", "abc123", "test-org/test-repo")

                mock_warn.assert_called_once()
                assert "Failed to send notification" in mock_warn.call_args[0][0]

    def test_delete_branch_impl(self):
        """Test branch deletion implementation."""
        mock_repo = Mock()
        mock_ref = Mock()

        self.client.client.get_repo.return_value = mock_repo
        mock_repo.get_git_ref.return_value = mock_ref

        self.client._delete_branch_impl("test-org", "test-repo", "test-branch")

        mock_repo.get_git_ref.assert_called_once_with("heads/test-branch")
        mock_ref.delete.assert_called_once()

    def test_notify_stale_branch_impl(self):
        """Test stale branch notification implementation."""
        mock_repo = Mock()
        mock_commit = Mock()

        self.client.client.get_repo.return_value = mock_repo
        mock_repo.get_commit.return_value = mock_commit

        self.client._notify_stale_branch_impl(
            "Stale branch message", "abc123", "test-org/test-repo"
        )

        mock_repo.get_commit.assert_called_once_with("abc123")
        mock_commit.create_comment.assert_called_once_with(body="Stale branch message")

    def test_close_success(self):
        """Test successful client close."""
        with patch("branch_manager.git.github.main.info") as mock_info:
            self.client.close()

            self.client.client.close.assert_called_once()
            mock_info.assert_called_once_with("GitHub client connection closed")

    def test_close_with_exception(self):
        """Test client close with exception."""
        self.client.client.close.side_effect = Exception("Close error")

        with patch("branch_manager.git.github.main.warn") as mock_warn:
            self.client.close()

            mock_warn.assert_called_once()
            assert "Error closing GitHub client" in mock_warn.call_args[0][0]

    def test_close_no_client(self):
        """Test close when client is None."""
        self.client.client = None

        # Should not raise an exception
        self.client.close()


class TestGitHubClientIntegration:
    """Integration tests for GitHubClient that test method interactions."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch("branch_manager.git.github.main.Github"):
            self.client = GitHubClient("test_token")

    def test_repository_listing_filters_correctly(self):
        """Test that repository listing properly filters archived and disabled repos."""
        # Create a mix of repository types
        repos = []
        for i in range(5):
            repo = Mock()
            repo.name = f"repo{i}"
            repo.archived = i == 1  # repo1 is archived
            repo.disabled = i == 3  # repo3 is disabled
            repos.append(repo)

        mock_org = Mock()
        mock_org.get_repos.return_value = repos
        self.client.client.get_organization.return_value = mock_org

        with patch("branch_manager.git.github.main.info"):
            with patch("branch_manager.git.github.main.debug"):
                result = self.client._list_all_repositories("test-org")

                # Should return repo0, repo2, repo4 (skip repo1=archived, repo3=disabled)
                assert result == ["repo0", "repo2", "repo4"]

    def test_error_handling_consistency(self):
        """Test that error handling is consistent across methods."""
        # Test that all methods handle 404 errors consistently
        exception_404 = GithubException(404, "Not Found", {})

        # Test organization not found
        self.client.client.get_organization.side_effect = exception_404
        with patch("branch_manager.git.github.main.error"):
            assert self.client._list_all_repositories("missing-org") == []

        # Test repository not found
        self.client.client.get_repo.side_effect = exception_404
        with patch("branch_manager.git.github.main.error"):
            assert self.client._list_all_branches("org", "missing-repo") == []
            assert self.client._get_latest_commit("org", "missing-repo", "branch") is None

    def test_commit_data_structure(self):
        """Test that commit data structure is consistent."""
        # Mock the complete chain for getting commit data
        mock_repo = Mock()
        mock_branch = Mock()
        mock_commit = Mock()

        mock_commit.sha = "abc123def456"
        mock_commit.commit.message = "Fix critical bug"
        mock_commit.commit.author.name = "developer"
        mock_commit.commit.author.date = Mock()
        mock_commit.commit.author.date.isoformat.return_value = "2023-06-15T14:30:00Z"
        mock_commit.author.login = "developer"  # Mock the login field that the code actually uses

        mock_branch.commit = mock_commit
        mock_repo.get_branch.return_value = mock_branch
        self.client.client.get_repo.return_value = mock_repo

        with patch("branch_manager.git.github.main.info"):
            with patch("branch_manager.git.github.main.debug"):
                commit_data = self.client._get_latest_commit("test-org", "test-repo", "main")

                # Verify all required fields are present
                required_fields = ["repo", "branch", "sha", "message", "author", "date"]
                for field in required_fields:
                    assert field in commit_data

                # Verify data types and format
                assert isinstance(commit_data["repo"], str)
                assert isinstance(commit_data["branch"], str)
                assert isinstance(commit_data["sha"], str)
                assert isinstance(commit_data["message"], str)
                assert isinstance(commit_data["author"], str)
                assert isinstance(commit_data["date"], str)

                # Verify specific values
                assert commit_data["repo"] == "test-org/test-repo"
                assert commit_data["branch"] == "main"
                assert commit_data["sha"] == "abc123def456"
