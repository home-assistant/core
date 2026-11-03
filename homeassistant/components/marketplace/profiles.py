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

    A field with several URLs tries them in order, a mirror that is down or
    behind falls back to the next one.
    """

    id: str
    # Who runs the endpoints, the user trusts them with all Marketplace traffic
    operator: str
    # The GitHub REST API, aiogithubapi takes a single base URL
    api: str
    # Only GitHub itself gets the token of a connected account
    uses_github_account: bool = False
    # Archives and release assets
    github: Sequence[str]
    # The content of single files
    raw: Sequence[str]
    catalog: Sequence[str]
    # Where to look when a check fails, by the health check it belongs to
    status_pages: dict[str, str] = field(default_factory=dict)
    # Suggested to users in these countries when the catalog is out of reach
    countries: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Turn a single URL into a sequence, the rest of the code iterates."""
        for endpoint in Endpoint:
            if isinstance(urls := getattr(self, endpoint), str):
                object.__setattr__(self, endpoint, (urls,))

    def bases(self, endpoint: Endpoint) -> tuple[str, ...]:
        """Return the base URLs of an endpoint, in the order to try them."""
        return tuple(getattr(self, endpoint))


GITHUB_STATUS = "https://www.githubstatus.com/"

PROFILES: dict[str, DownloadProfile] = {
    profile.id: profile
    for profile in (
        DownloadProfile(
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
        ),
        DownloadProfile(
            id="hasscn",
            operator="the Home Assistant China community (hasscn.top)",
            api="https://ghapi.hacs.vip",
            github=("https://ghrp2.hacs.vip", "https://ghrp.hacs.vip"),
            raw=("https://ghrp2.hacs.vip/raw", "https://ghrp.hacs.vip/raw"),
            # The mirror of the catalog can lag behind, the original is the fallback
            catalog=("https://data-v2.hacs.vip", "https://data-v2.hacs.xyz"),
            countries=frozenset({"CN"}),
        ),
    )
}


def get_profile(profile_id: str | None) -> DownloadProfile:
    """Return a profile by id, the default for one that is not (or no longer) known."""
    return PROFILES.get(profile_id or DEFAULT_PROFILE, PROFILES[DEFAULT_PROFILE])


class ProfileEndpoints:
    """The endpoints of the active profile, as the downloads go through them.

    Starts at the base that worked last, so a mirror that is down costs one
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
        if (preferred := self._preferred.get(endpoint)) in bases:
            bases.remove(preferred)
            bases.insert(0, preferred)
        return bases

    def worked(self, endpoint: Endpoint, base: str, failed: Sequence[str]) -> None:
        """Remember the base that answered, after the ones that did not."""
        self._preferred[endpoint] = base
        if not failed or endpoint in self._fallback_logged:
            return

        self._fallback_logged.add(endpoint)
        LOGGER.info(
            "%s failed, the Marketplace uses %s instead",
            ", ".join(failed),
            base,
        )


@callback
def async_suggest_profile(hass: HomeAssistant, active: DownloadProfile) -> None:
    """Suggest a profile meant for the country of the user, if there is one."""
    country = hass.config.country
    for profile in PROFILES.values():
        if profile.id == active.id or country not in profile.countries:
            continue

        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{PROFILE_ISSUE_PREFIX}{profile.id}",
            data={"profile": profile.id},
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
        if issue is not None and issue.dismissed_version is None:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
