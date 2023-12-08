"""Helpers for generating issues."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import DOMAIN
from .helpers import Observation


def raise_mirrored_entries(
    hass: HomeAssistant, observations: list[Observation], text: str = ""
) -> None:
    """If there are mirrored entries, the user is probably using a workaround for a patched bug."""
    if len(observations) != 2:
        return
    if observations[0].is_mirror(observations[1]):
        ir.async_create_issue(
            hass,
            DOMAIN,
            "mirrored_entry/" + text,
            breaks_in_ha_version="2022.10.0",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="manual_migration",
            translation_placeholders={"entity": text},
            learn_more_url="https://github.com/home-assistant/core/pull/67631",
        )


# Should deprecate in some future version (2022.10 at time of writing) & make prob_given_false required in schemas.
def raise_no_prob_given_false(hass: HomeAssistant, text: str) -> None:
    """In previous 2022.9 and earlier, prob_given_false was optional and had a default version."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"no_prob_given_false/{text}",
        breaks_in_ha_version="2022.10.0",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="no_prob_given_false",
        translation_placeholders={"entity": text},
        learn_more_url="https://github.com/home-assistant/core/pull/67631",
    )
