"""Test the __init__ module for the HALO Home integration."""

import json
from unittest.mock import patch

from halohome import LocationConnection
import pytest

from homeassistant.components.halohome.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder

from tests.common import MockConfigEntry
from tests.components.halohome.test_config_flow import CONFIG_ENTRY


class _MockConnection(LocationConnection):
    async def set_brightness(self, device_id: int, brightness: int) -> bool:
        return True

    async def set_color_temp(self, device_id: int, brightness: int) -> bool:
        return True


@patch("halohome.LocationConnection", _MockConnection)
async def setup_halo(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the HALO Home integration."""

    hass.config.components.add(DOMAIN)
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_ENTRY,
    )

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()

    return config_entry


async def test_setup_entry(hass: HomeAssistant):
    """Test setting up the HALO Home integration and dumping state to JSON."""
    await setup_halo(hass)

    try:
        json.dumps(hass.states.async_all(), cls=JSONEncoder)
    except Exception:
        pytest.fail(
            "Unable to convert all demo entities to JSON. "
            "Wrong data in state machine!"
        )


async def test_unload_entry(hass: HomeAssistant):
    """Test unloading the HALO Home integration."""
    entry = await setup_halo(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
