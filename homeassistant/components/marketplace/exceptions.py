"""Custom exceptions for the Marketplace."""

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


class MarketplaceError(HomeAssistantError):
    """The base of every error the Marketplace raises.

    With a translation key its message comes from the strings of the
    Marketplace, in English in the log and translated where the user sees it.
    """


class RepositoryArchivedError(MarketplaceError):
    """For repositories that are archived."""


class GitHubRateLimitError(MarketplaceError):
    """For GitHub API calls refused because the rate limit ran out."""

    rate_limit_translation_key = "rate_limited"

    def __init__(self) -> None:
        """Initialize the exception, what GitHub answered is the one it came from."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key=self.rate_limit_translation_key,
        )


class GitHubAnonymousRateLimitError(GitHubRateLimitError):
    """For a rate limit hit without a GitHub connection.

    It fails the action that hit it, the Marketplace itself carries on.
    """

    rate_limit_translation_key = "github_rate_limited"


class CatalogContentUnresolvedError(MarketplaceError):
    """For a catalog install the repository archive can not resolve.

    Nothing is written yet when it is raised, the install goes through the
    GitHub API instead.
    """


class ReplacesBuiltInNotConfirmedError(MarketplaceError):
    """For a first install over a built-in integration that was not confirmed."""

    def __init__(self, repository: str, domain: str) -> None:
        """Initialize the exception."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="replaces_built_in_not_confirmed",
            translation_placeholders={"repository": repository, "domain": domain},
        )
        self.domain = domain


class RepositoryBusyError(MarketplaceError):
    """For a repository that is being installed, it can not change meanwhile."""

    def __init__(self, repository: str) -> None:
        """Initialize the exception."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="repository_busy",
            translation_placeholders={"repository": repository},
        )


class NotModifiedError(MarketplaceError):
    """For responses that are not modified."""


class ExpectedError(MarketplaceError):
    """For a repository the Marketplace skips on purpose."""


class RepositoryExistsError(MarketplaceError):
    """For repositories that already exist."""


class ExecutionInProgressError(MarketplaceError):
    """For a queue that is already running."""


class AppRepositoryError(MarketplaceError):
    """For a repository of apps, the Marketplace does not manage those."""

    def __init__(self, repository: str) -> None:
        """Initialize the exception."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="app_repository",
            translation_placeholders={"repository": repository},
        )


class CoreRepositoryError(MarketplaceError):
    """For the repository of Home Assistant itself."""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__(translation_domain=DOMAIN, translation_key="core_repository")
