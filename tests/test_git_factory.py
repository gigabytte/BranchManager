"""Tests for the GitClientFactory."""

import pytest

from branch_manager.git.base import BaseGitClient
from branch_manager.git.factory import GitClientFactory
from branch_manager.git.github.main import GitHubClient


class TestGitClientFactory:
    """Test cases for GitClientFactory."""

    def test_create_client_github(self):
        """Test creating a GitHub client."""
        token = "test_token"
        client = GitClientFactory.create_client("github", token)

        assert isinstance(client, GitHubClient)
        assert client.access_token == token

    def test_create_client_unsupported_provider(self):
        """Test creating a client for an unsupported provider."""
        with pytest.raises(ValueError, match="Unsupported provider 'unsupported'"):
            GitClientFactory.create_client("unsupported", "token")

    def test_create_client_case_sensitive(self):
        """Test that provider names are case-sensitive."""
        with pytest.raises(ValueError, match="Unsupported provider 'GitHub'"):
            GitClientFactory.create_client("GitHub", "token")

    def test_get_supported_providers(self):
        """Test getting list of supported providers."""
        providers = GitClientFactory.get_supported_providers()

        assert isinstance(providers, list)
        assert "github" in providers
        assert len(providers) >= 1

    def test_factory_registry_structure(self):
        """Test that the factory registry is properly structured."""
        assert hasattr(GitClientFactory, "_clients")
        assert isinstance(GitClientFactory._clients, dict)
        assert "github" in GitClientFactory._clients
        assert issubclass(GitClientFactory._clients["github"], BaseGitClient)

    def test_factory_extensibility(self):
        """Test that the factory can be extended with new providers."""

        # Create a mock client class
        class MockClient(BaseGitClient):
            def __init__(self, access_token: str):
                super().__init__(access_token)

            def is_authenticated(self) -> bool:
                return True

            def _list_all_repositories(self, org_name: str) -> list[str]:
                return []

            def _list_all_branches(self, org_name: str, repo_name: str) -> list[str]:
                return []

            def _get_latest_commit(self, org_name: str, repo_name: str, branch_name: str) -> dict:
                return {}

            def _delete_branch_impl(self, org_name: str, repo_name: str, branch_name: str) -> None:
                pass

            def _notify_stale_branch_impl(self, message: str, sha: str, repo: str) -> None:
                pass

            def close(self) -> None:
                pass

        # Temporarily add mock provider
        original_clients = GitClientFactory._clients.copy()
        try:
            GitClientFactory._clients["mock"] = MockClient

            # Test that it works
            providers = GitClientFactory.get_supported_providers()
            assert "mock" in providers

            client = GitClientFactory.create_client("mock", "test_token")
            assert isinstance(client, MockClient)

        finally:
            # Restore original registry
            GitClientFactory._clients = original_clients

    def test_error_message_includes_supported_providers(self):
        """Test that error message includes list of supported providers."""
        with pytest.raises(ValueError) as exc_info:
            GitClientFactory.create_client("invalid", "token")

        error_message = str(exc_info.value)
        assert "Unsupported provider 'invalid'" in error_message
        assert "Supported:" in error_message
        assert "github" in error_message
