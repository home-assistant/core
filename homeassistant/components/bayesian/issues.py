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
