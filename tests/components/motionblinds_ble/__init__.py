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

from tests.common import MockConfigEntry


async def setup_platform(
    hass: HomeAssistant,
    platforms: list[Platform],
    blind_type: MotionBlindType = MotionBlindType.ROLLER,
) -> MockConfigEntry:
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
