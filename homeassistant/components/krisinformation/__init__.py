"""The krisinformation integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.GEO_LOCATION]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up krisinformation from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    _LOGGER.debug("Feed entity manager added for %s", entry.entry_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def _generate_mock_event(identifier, headline):
    return {
        "Identifier": identifier,
        "Headline": headline,
        "Area": [
            {
                "Type": "County",
                "Description": "Västra Götalands län",
                "GeometryInformation": {
                    "PoleOfInInaccessibility": {"coordinates": [57.7, 9.11]}
                },
            }
        ],
        "Web": "krisinformation.se",
        "Published": "2023-03-29T11:02:11+02:00",
        "PushMessage": "Test message",
    }
