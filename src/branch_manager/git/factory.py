"""Client factory for different git hosting providers."""

from branch_manager.git.base import BaseGitClient
from branch_manager.git.github.main import GitHubClient


class GitClientFactory:
    """Factory for creating git hosting API clients."""

    # Registry of available clients
    _clients: dict[str, type[BaseGitClient]] = {
        "github": GitHubClient,
        # Future providers can be added here:
        # "gitlab": GitLabClient,
        # "bitbucket": BitbucketClient,
    }

    @classmethod
    def create_client(cls, provider: str, access_token: str) -> BaseGitClient:
        """Create a client for the specified provider."""
        if provider not in cls._clients:
            supported = ", ".join(cls._clients.keys())
            raise ValueError(f"Unsupported provider '{provider}'. Supported: {supported}")

        client_class = cls._clients[provider]
        return client_class(access_token)

    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported providers."""
        return list(cls._clients.keys())

    @classmethod
    def register_provider(cls, name: str, client_class: type[BaseGitClient]) -> None:
        """Register a new provider (for future extensibility)."""
        cls._clients[name] = client_class
