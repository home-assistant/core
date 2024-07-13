"""Tests for the Motionblinds Bluetooth integration."""

from homeassistant.components.motionblinds_ble import async_setup_entry
from homeassistant.components.motionblinds_ble.const import CONF_LOCAL_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.common import MockConfigEntry

FIXTURE_SERVICE_INFO = BluetoothServiceInfo(
    name="MOTION_CCCC",
    address="cc:cc:cc:cc:cc:cc",
    rssi=-63,
    service_data={},
    manufacturer_data={},
    service_uuids=[],
    source="local",
)


async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> str:
    """Mock a fully setup config entry."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await async_setup_entry(hass, mock_config_entry)
    await hass.async_block_till_done()

    return str(mock_config_entry.data[CONF_LOCAL_NAME]).lower().replace(" ", "_")
