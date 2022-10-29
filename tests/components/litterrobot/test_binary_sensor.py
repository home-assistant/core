"""Test the Litter-Robot binary sensor entity."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.binary_sensor import (
    DOMAIN as PLATFORM_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant

from .conftest import setup_integration


@pytest.mark.freeze_time("2022-09-18 23:00:44+00:00")
async def test_binary_sensors(
    hass: HomeAssistant,
    mock_account: MagicMock,
    entity_registry_enabled_by_default: AsyncMock,
) -> None:
    """Tests binary sensors."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    state = hass.states.get("binary_sensor.test_sleeping")
    assert state.state == "off"
    state = hass.states.get("binary_sensor.test_sleep_mode")
    assert state.state == "on"
    state = hass.states.get("binary_sensor.test_power_status")
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.PLUG
    assert state.state == "on"
