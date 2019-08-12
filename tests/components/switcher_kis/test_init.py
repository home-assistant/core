"""Test cases for the switcher_kis component."""

from typing import Any, Generator

from homeassistant.components.switcher_kis import (DOMAIN, DATA_DEVICE)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from .consts import (
    DUMMY_AUTO_OFF_SET, DUMMY_DEVICE_ID, DUMMY_DEVICE_NAME,
    DUMMY_DEVICE_STATE, DUMMY_ELECTRIC_CURRENT, DUMMY_IP_ADDRESS,
    DUMMY_MAC_ADDRESS, DUMMY_PHONE_ID, DUMMY_POWER_CONSUMPTION,
    DUMMY_REMAINING_TIME, MANDATORY_CONFIGURATION)


async def test_failed_config(hass: HomeAssistantType) -> None:
    """Test failed configuration."""
    assert await async_setup_component(
        hass, DOMAIN, MANDATORY_CONFIGURATION) is False


async def test_minimal_config(hass: HomeAssistantType,
                              mock_bridge: Generator[None, Any, None]
                              ) -> None:
    """Test setup with configuration minimal entries."""
    assert await async_setup_component(hass, DOMAIN, MANDATORY_CONFIGURATION)


async def test_discovery_data_bucket(
        hass: HomeAssistantType,
        mock_bridge: Generator[None, Any, None]
        ) -> None:
    """Test the event send with the updated device."""
    assert await async_setup_component(
        hass, DOMAIN, MANDATORY_CONFIGURATION)

    await hass.async_block_till_done()

    device = hass.data[DOMAIN].get(DATA_DEVICE)
    assert device.device_id == DUMMY_DEVICE_ID
    assert device.ip_addr == DUMMY_IP_ADDRESS
    assert device.mac_addr == DUMMY_MAC_ADDRESS
    assert device.name == DUMMY_DEVICE_NAME
    assert device.state == DUMMY_DEVICE_STATE
    assert device.remaining_time == DUMMY_REMAINING_TIME
    assert device.auto_off_set == DUMMY_AUTO_OFF_SET
    assert device.power_consumption == DUMMY_POWER_CONSUMPTION
    assert device.electric_current == DUMMY_ELECTRIC_CURRENT
    assert device.phone_id == DUMMY_PHONE_ID
