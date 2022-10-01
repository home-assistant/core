"""Helpers for generating repairs."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry

from . import DOMAIN


def raise_mirrored_entries(hass: HomeAssistant, observations, text: str = "") -> None:
    """If there are mirrored entries, the user is probably using a workaround for a patched bug."""
    if len(observations) != 2:
        return
    true_sums_1: bool = (
        round(
            observations[0]["prob_given_true"] + observations[1]["prob_given_true"], 1
        )
        == 1.0
    )
    false_sums_1: bool = (
        round(
            observations[0]["prob_given_false"] + observations[1]["prob_given_false"], 1
        )
        == 1.0
    )
    same_states: bool = observations[0]["platform"] == observations[1]["platform"]
    if true_sums_1 & false_sums_1 & same_states:
        issue_registry.async_create_issue(
            hass,
            DOMAIN,
            "mirrored_entry/" + text,
            breaks_in_ha_version="2022.10.0",
            is_fixable=False,
            severity=issue_registry.IssueSeverity.WARNING,
            translation_key="manual_migration",
            translation_placeholders={"entity": text},
            learn_more_url="https://github.com/home-assistant/core/pull/67631",
        )


# Should deprecate in some future version (2022.10 at time of writing) & make prob_given_false required in schemas.
def raise_no_prob_given_false(hass: HomeAssistant, observation, text: str) -> None:
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
        learn_more_url="https://github.com/home-assistant/core/pull/67631",
    )
