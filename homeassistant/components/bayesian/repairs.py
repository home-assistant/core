"""Helpers for generating repairs."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry

from . import DOMAIN
from .helpers import Observation


def raise_mirrored_entries(
    hass: HomeAssistant, observations: list[Observation], text: str = ""
) -> None:
    """If there are mirrored entries, the user is probably using a workaround for a patched bug.

    In rare cases the user may have happened to configure 2 entries for a non binary sensor and
    is ignoring the other possible states - this will still technically be an incorrect (but
    working) config as prob_given_true should not sum to 1 if more than the 2 states are possible.
    """
    if len(observations) != 2:
        return
    if observations[0].is_mirror(observations[1]):
        issue_registry.async_create_issue(
            hass,
            DOMAIN,
            "mirrored_entry/" + text,
            breaks_in_ha_version="2022.10.0",
            is_fixable=False,
            severity=issue_registry.IssueSeverity.WARNING,
            translation_key="manual_migration",
            translation_placeholders={"entity": text},
            learn_more_url="https://www.home-assistant.io/blog/2022/10/05/release-202210/#breaking-changes",
        )


# Should deprecate in some future version (2022.10 at time of writing) & make prob_given_false required in schemas.
def raise_no_prob_given_false(hass: HomeAssistant, text: str) -> None:
    """In previous 2022.9 and earlier, prob_given_false was optional and had a default version."""
    issue_registry.async_create_issue(
        hass,
        DOMAIN,
        f"no_prob_given_false/{text}",
        breaks_in_ha_version="2022.10.0",
        is_fixable=False,
        severity=issue_registry.IssueSeverity.ERROR,
        translation_key="no_prob_given_false",
        translation_placeholders={"entity": text},
        learn_more_url="https://www.home-assistant.io/blog/2022/10/05/release-202210/#breaking-changes",
    )
