"""Helpers for generating issues."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .helpers import Observation


def raise_mirrored_entries(
    hass: HomeAssistant, observations: list[Observation], text: str = ""
) -> None:
    """Raise an issue if mirrored entries suggest a patched bug workaround."""
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


# Should deprecate in some future version (2022.10 at time of
# writing) & make prob_given_false required in schemas.
def raise_no_prob_given_false(hass: HomeAssistant, text: str) -> None:
    """Raise issue: prob_given_false was optional before 2022.10."""
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
