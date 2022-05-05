"""Fixtures for the Sensibo integration."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG
from .response import DATA_FROM_API

from tests.common import MockConfigEntry


@pytest.fixture
async def load_int(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Sensibo integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="username",
        version=2,
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
