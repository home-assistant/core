"""Test the __init__ module for the HALO Home integration."""

import json
from unittest.mock import patch

from halohome import LocationConnection
import pytest

from homeassistant.components.halohome.const import CONF_LOCATIONS, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder

from tests.common import MockConfigEntry
from tests.components.halohome.test_config_flow import CONFIG_ENTRY, LOCATIONS

EMPTY_ENTRY = {**CONFIG_ENTRY, CONF_LOCATIONS: {}}


class _MockConnection(LocationConnection):
    async def set_brightness(self, device_id: int, brightness: int) -> bool:
        return True

    async def set_color_temp(self, device_id: int, brightness: int) -> bool:
        return True


async def _list_devices(email: str, password: str):
    return LOCATIONS


async def _list_devices_error(email: str, password: str):
    raise OSError("Cannot connect to host ... [Temporary failure in name resolution]")


@patch("halohome.LocationConnection", _MockConnection)
async def setup_halo(
    hass: HomeAssistant,
    data=CONFIG_ENTRY,
    list_error: bool = False,
) -> MockConfigEntry:
    """Set up the HALO Home integration."""

    list_patch = _list_devices_error if list_error else _list_devices

    with patch("halohome.list_devices", list_patch):
        hass.config.components.add(DOMAIN)
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=data,
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


async def test_device_refresh(hass: HomeAssistant):
    """Test setting up the HALO Home integration with refreshed devices."""
    entry = await setup_halo(hass, data=EMPTY_ENTRY)

    assert entry.data == CONFIG_ENTRY
    assert len(hass.data[DOMAIN][entry.entry_id].devices) == 1


async def test_device_refresh_error(hass: HomeAssistant):
    """Test setting up the HALO Home integration with error on device refresh."""
    entry = await setup_halo(hass, data=EMPTY_ENTRY, list_error=True)

    assert entry.data == EMPTY_ENTRY
    assert len(hass.data[DOMAIN][entry.entry_id].devices) == 0


async def test_unload_entry(hass: HomeAssistant):
    """Test unloading the HALO Home integration."""
    entry = await setup_halo(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
