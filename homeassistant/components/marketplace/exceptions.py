"""Custom exceptions for the Marketplace."""


class MarketplaceError(Exception):
    """Super basic."""


class RepositoryArchivedError(MarketplaceError):
    """For repositories that are archived."""


class GitHubRateLimitError(MarketplaceError):
    """For GitHub API calls refused because the rate limit ran out."""


class GitHubAnonymousRateLimitError(GitHubRateLimitError):
    """For a rate limit hit without a GitHub connection.

    It fails the action that hit it, the Marketplace itself carries on.
    """


class CatalogContentUnresolvedError(MarketplaceError):
    """For a catalog install the repository archive can not resolve.

    Nothing is written yet when it is raised, the install goes through the
    GitHub API instead.
    """


class ReplacesBuiltInNotConfirmedError(MarketplaceError):
    """For a first install over a built-in integration that was not confirmed."""

    def __init__(self, domain: str) -> None:
        """Initialize the exception."""
        super().__init__(
            f"Replacing the built-in '{domain}' integration was not confirmed"
        )
        self.domain = domain


class NotModifiedError(MarketplaceError):
    """For responses that are not modified."""


class ExpectedError(MarketplaceError):
    """For stuff that are expected."""


class RepositoryExistsError(MarketplaceError):
    """For repositories that already exist."""


class ExecutionInProgressError(MarketplaceError):
    """Exception to raise if execution is still in progress."""


class AppRepositoryError(MarketplaceError):
    """Exception to raise when user tries to add an app repository."""

    exception_message = (
        "The repository does not seem to be an integration, "
        "but an app repository. The Marketplace does not manage apps."
    )

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__(self.exception_message)


class CoreRepositoryError(MarketplaceError):
    """Exception to raise when user tries to add the home-assistant/core repository."""

    exception_message = (
        "You can not add homeassistant/core, to use core integrations "
        "check the Home Assistant documentation for how to add them."
    )

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__(self.exception_message)
