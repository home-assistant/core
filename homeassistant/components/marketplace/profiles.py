"""Download profiles, where the Marketplace gets its content from.

Every host the Marketplace downloads from is named here and nowhere else. Our
own setup is just the default profile, another profile sends the same requests,
with the same paths, to other endpoints.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .utils.logger import LOGGER

DEFAULT_PROFILE = "default"
PROFILE_ISSUE_PREFIX = "download_profile_"


class Endpoint(StrEnum):
    """The kinds of content a profile has endpoints for."""

    GITHUB = "github"
    RAW = "raw"
    CATALOG = "catalog"


@dataclass(frozen=True, kw_only=True)
class DownloadProfile:
    """The endpoints the Marketplace gets its content from.

    An endpoint takes one URL, or several to try in order: a relay that is
    down falls back to the next one.
    """

    # Stored in the options of the config entry
    id: str

    # Who runs the endpoints. The user trusts them with all Marketplace
    # traffic, so the options and the repair name them.
    operator: str

    # The GitHub REST API. A single URL, aiogithubapi takes one base URL.
    api: str

    # Only GitHub itself gets the token of a connected GitHub account
    uses_github_account: bool = False

    # Repository archives and release assets
    github: Sequence[str]

    # The content of single files, such as hacs.json and README.md
    raw: Sequence[str]

    # The catalog of repositories, and the removed and critical lists
    catalog: Sequence[str]

    # The status page to point at when a health check fails, by check
    status_pages: dict[str, str] = field(default_factory=dict)

    # Suggested through a repair to users in these countries, when the
    # catalog cannot be reached
    countries: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Turn an endpoint with a single URL into a sequence of one.

        The rest of the code can then always loop over the URLs.
        """
        for endpoint in Endpoint:
            urls = getattr(self, endpoint)
            if isinstance(urls, str):
                # The dataclass is frozen, this is how it can still be set
                object.__setattr__(self, endpoint, (urls,))

    def bases(self, endpoint: Endpoint) -> tuple[str, ...]:
        """Return the base URLs of an endpoint, in the order to try them."""
        return tuple(getattr(self, endpoint))


GITHUB_STATUS = "https://www.githubstatus.com/"

GITHUB = DownloadProfile(
    id=DEFAULT_PROFILE,
    operator="GitHub and the Open Home Foundation",
    api="https://api.github.com",
    uses_github_account=True,
    github="https://github.com",
    raw="https://raw.githubusercontent.com",
    catalog="https://data-v2.hacs.xyz",
    status_pages={
        "api": GITHUB_STATUS,
        Endpoint.GITHUB: GITHUB_STATUS,
        Endpoint.CATALOG: "https://www.cloudflarestatus.com/",
    },
)

# The relays serve the same paths as GitHub, raw content below /raw. A public
# third-party relay is the last resort for downloads, it takes the full URL.
CHINA_RELAYS = DownloadProfile(
    id="hasscn",
    operator="the Home Assistant China community (hasscn.top)",
    api="https://ghapi.hacs.vip",
    github=(
        "https://ghrp2.hacs.vip",
        "https://ghrp.hacs.vip",
        "https://gh-proxy.org/https://github.com",
    ),
    raw=(
        "https://ghrp2.hacs.vip/raw",
        "https://ghrp.hacs.vip/raw",
        "https://gh-proxy.org/https://raw.githubusercontent.com",
    ),
    # data-v2.hasscn.top only answers requests that carry the User-Agent of
    # the Marketplace. The original is the last fallback.
    catalog=(
        "https://data-v2.hasscn.top",
        "https://data-v2.hacs.vip",
        "https://data-v2.hacs.xyz",
    ),
    countries=frozenset({"CN"}),
)

# The profiles a user can choose from, by id
PROFILES: dict[str, DownloadProfile] = {
    profile.id: profile for profile in (GITHUB, CHINA_RELAYS)
}


def get_profile(profile_id: str | None) -> DownloadProfile:
    """Return a profile by id, the default for one that is not (or no longer) known."""
    return PROFILES.get(profile_id or DEFAULT_PROFILE, GITHUB)


class ProfileEndpoints:
    """The endpoints of the active profile, as the downloads go through them.

    Starts at the base that worked last, so a relay that is down costs one
    failed request, not one on every download. A reload starts over.
    """

    def __init__(self, profile: DownloadProfile) -> None:
        """Initialize."""
        self.profile = profile
        self._preferred: dict[Endpoint, str] = {}
        self._fallback_logged: set[Endpoint] = set()

    def bases(self, endpoint: Endpoint) -> list[str]:
        """Return the base URLs to try, the one that worked last first."""
        bases = list(self.profile.bases(endpoint))

        preferred = self._preferred.get(endpoint)
        if preferred in bases:
            bases.remove(preferred)
            bases.insert(0, preferred)

        return bases

    def worked(self, endpoint: Endpoint, base: str, failed: Sequence[str]) -> None:
        """Remember the base that answered, after the ones that did not."""
        self._preferred[endpoint] = base

        # Once per endpoint, not on every download that falls back
        if not failed or endpoint in self._fallback_logged:
            return

        self._fallback_logged.add(endpoint)
        LOGGER.info(
            "%s failed, the Marketplace uses %s instead",
            ", ".join(failed),
            base,
        )


@callback
def async_suggest_profile(
    hass: HomeAssistant, entry_id: str, active: DownloadProfile
) -> None:
    """Suggest a profile meant for the country of the user, if there is one."""
    country = hass.config.country

    for profile in PROFILES.values():
        if profile.id == active.id or country not in profile.countries:
            continue

        async_create_profile_suggestion(hass, entry_id, profile)


@callback
def async_create_profile_suggestion(
    hass: HomeAssistant, entry_id: str, profile: DownloadProfile
) -> None:
    """Create the issue that suggests a profile."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{PROFILE_ISSUE_PREFIX}{profile.id}",
        config_entry_id=entry_id,
        data={"entry_id": entry_id, "profile": profile.id},
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="download_profile",
        translation_placeholders={"operator": profile.operator},
    )


@callback
def async_withdraw_profile_suggestions(hass: HomeAssistant) -> None:
    """Remove the suggestions of a profile, the catalog can be reached.

    Not the ones the user ignored, deleting an issue forgets the ignore.
    """
    issue_registry = ir.async_get(hass)

    for profile_id in PROFILES:
        issue_id = f"{PROFILE_ISSUE_PREFIX}{profile_id}"

        issue = issue_registry.async_get_issue(DOMAIN, issue_id)
        if issue is None or issue.dismissed_version is not None:
            continue

        ir.async_delete_issue(hass, DOMAIN, issue_id)
