"""Fixtures for the Sensibo integration."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG
from .response import DATA_FROM_API

from tests.common import MockConfigEntry


@pytest.fixture
async def load_int(  # pylint: disable=dangerous-default-value
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

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
