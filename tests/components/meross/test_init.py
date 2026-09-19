"""Test the Meross Bluetooth integration setup."""

import pytest

from homeassistant.components.meross.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant

from . import MEROSS_MS120_ADDRESS, MEROSS_MS120_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("mock_bluetooth")
async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up and unloading a config entry."""
    inject_bluetooth_service_info(hass, MEROSS_MS120_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aabbccddeeff",
        title="Meross MS120",
        data={
            CONF_ADDRESS: MEROSS_MS120_ADDRESS,
            CONF_MODEL: "ms120",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_bluetooth")
async def test_async_setup_entry_device_not_found(hass: HomeAssistant) -> None:
    """Test setup fails when the BLE device is not in the cache."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aabbccddeeff",
        title="Meross MS120",
        data={
            CONF_ADDRESS: MEROSS_MS120_ADDRESS,
            CONF_MODEL: "ms120",
        },
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
