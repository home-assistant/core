"""Tests for the Motionblinds Bluetooth integration."""

from unittest.mock import patch

from motionblindsble.const import MotionBlindType

from homeassistant.components.motionblinds_ble import async_setup_entry
from homeassistant.components.motionblinds_ble.const import (
    CONF_BLIND_TYPE,
    CONF_LOCAL_NAME,
    CONF_MAC_CODE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.common import MockConfigEntry

SERVICE_INFO = BluetoothServiceInfo(
    name="MOTION_CCCC",
    address="cc:cc:cc:cc:cc:cc",
    rssi=-63,
    service_data={},
    manufacturer_data={
        1062: b"\x02\x07d\x02\x05\x01\x02\x08\x00\x02\t\x01\x04\x06\x10\x00\x01"
    },
    service_uuids=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"],
    source="local",
)


async def setup_platform(
    hass: HomeAssistant,
    platforms: list[Platform],
    blind_type: MotionBlindType = MotionBlindType.ROLLER,
) -> tuple[MockConfigEntry, str]:
    """Mock a fully setup config entry."""

    config_entry = MockConfigEntry(
        title="mock_title",
        domain=DOMAIN,
        unique_id="cc:cc:cc:cc:cc:cc",
        data={
            CONF_ADDRESS: "cc:cc:cc:cc:cc:cc",
            CONF_LOCAL_NAME: "Motionblind CCCC",
            CONF_MAC_CODE: "CCCC",
            CONF_BLIND_TYPE: blind_type.name.lower(),
        },
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.motionblinds_ble.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

    return (
        config_entry,
        str(config_entry.data[CONF_LOCAL_NAME]).lower().replace(" ", "_"),
    )
