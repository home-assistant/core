"""Tests for the Motionblinds Bluetooth integration."""

from motionblindsble.const import MotionBlindType

from homeassistant.components.motionblinds_ble import async_setup_entry
from homeassistant.components.motionblinds_ble.const import (
    CONF_BLIND_TYPE,
    CONF_LOCAL_NAME,
    CONF_MAC_CODE,
    DOMAIN,
)
from homeassistant.const import CONF_ADDRESS
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

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await async_setup_entry(hass, config_entry)
    await hass.async_block_till_done()

    return (
        config_entry,
        str(config_entry.data[CONF_LOCAL_NAME]).lower().replace(" ", "_"),
    )
