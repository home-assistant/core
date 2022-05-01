"""Tests for the Sensibo integration."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .response import DATA_FROM_API

from tests.common import MockConfigEntry

ENTRY_CONFIG = {CONF_API_KEY: "1234567890"}


async def init_integration(  # pylint: disable=dangerous-default-value
    hass: HomeAssistant,
    config: dict[str, Any] = None,
    entry_id: str = "1",
    source: str = SOURCE_USER,
    version: int = 2,
    unique_id: str = "username",
    name: list[str, str] = ["Hallway", "Kitchen"],
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

    data_set = DATA_FROM_API
    data_set.parsed[name[0]] = DATA_FROM_API.parsed["ABC999111"]
    data_set.parsed[name[1]] = DATA_FROM_API.parsed["AAZZAAZZ"]
    setattr(data_set.parsed[name[0]], "name", name[0])
    setattr(data_set.parsed[name[1]], "name", name[1])
    setattr(data_set.parsed[name[0]], "id", name[0])
    setattr(data_set.parsed[name[1]], "id", name[1])

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
