"""Test the OKOK Scale init."""

import pytest

from homeassistant.components.okokscale.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import (
    OKOK_20_ADDRESS,
    OKOK_20_SERVICE_INFO,
    OKOK_C0_ADDRESS,
    OKOK_C0_SERVICE_INFO,
    OKOK_F0_ADDRESS,
    OKOK_F0_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    ("mock_config_entry", "service_info"),
    [
        (
            MockConfigEntry(domain=DOMAIN, unique_id=OKOK_F0_ADDRESS),
            OKOK_F0_SERVICE_INFO,
        ),
        (
            MockConfigEntry(domain=DOMAIN, unique_id=OKOK_20_ADDRESS),
            OKOK_20_SERVICE_INFO,
        ),
        (
            MockConfigEntry(domain=DOMAIN, unique_id=OKOK_C0_ADDRESS),
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
    # await setup_integration(hass, mock_config_entry)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
