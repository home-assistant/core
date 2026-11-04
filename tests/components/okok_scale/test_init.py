"""Test the OKOK Scale init."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info

from homeassistant.components.okok_scale.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import OKOK_20_SERVICE_INFO, OKOK_C0_SERVICE_INFO, OKOK_F0_SERVICE_INFO


@pytest.mark.parametrize(
    ("mock_config_entry", "service_info"),
    [
        (
            MockConfigEntry(domain=DOMAIN, unique_id=OKOK_F0_SERVICE_INFO.address),
            OKOK_F0_SERVICE_INFO,
        ),
        (
            MockConfigEntry(domain=DOMAIN, unique_id=OKOK_20_SERVICE_INFO.address),
            OKOK_20_SERVICE_INFO,
        ),
        (
            MockConfigEntry(domain=DOMAIN, unique_id=OKOK_C0_SERVICE_INFO.address),
            OKOK_C0_SERVICE_INFO,
        ),
    ],
)
async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    service_info: BluetoothServiceInfo,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "mock_config_entry",
    [
        MockConfigEntry(domain=DOMAIN, unique_id=OKOK_F0_SERVICE_INFO.address),
        MockConfigEntry(domain=DOMAIN, unique_id=OKOK_20_SERVICE_INFO.address),
        MockConfigEntry(domain=DOMAIN, unique_id=OKOK_C0_SERVICE_INFO.address),
    ],
)
async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
