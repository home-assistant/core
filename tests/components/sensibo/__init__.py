"""Tests for the Sensibo integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTRY_CONFIG = {CONF_API_KEY: "1234567890"}


async def init_integration(  # pylint: disable=dangerous-default-value
    hass: HomeAssistant,
    config: dict[str, Any] = None,
    entry_id: str = "1",
    source: str = SOURCE_USER,
    version: int = 2,
    unique_id: str = "username",
) -> MockConfigEntry:
    """Set up the Sensibo integration in Home Assistant."""
    if not config:
        config = ENTRY_CONFIG

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=source,
        data=config,
        entry_id=entry_id,
        unique_id=unique_id,
        version=version,
    )

    config_entry.add_to_hass(hass)

    return config_entry
