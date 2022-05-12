"""Test the Elro Connects setup."""

import copy
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.elro_connects.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from .test_common import MOCK_DEVICE_STATUS_DATA

from tests.common import async_fire_time_changed


@pytest.mark.parametrize(
    "sensor,enable,state1,state2,state3",
    [
        ("beganegrond_device_state", False, "NORMAL", "NORMAL", "unavailable"),
        ("eerste_etage_device_state", False, "ALARM", "ALARM", "ALARM"),
        ("zolder_device_state", False, None, "UNKNOWN", "UNKNOWN"),
        ("corner_device_state", False, "unavailable", "unavailable", "unavailable"),
        ("beganegrond_battery", False, "100", "100", "unavailable"),
        ("eerste_etage_battery", False, "75", "75", "75"),
        ("zolder_battery", False, None, "5", "5"),
        ("corner_battery", False, "unavailable", "unavailable", "unavailable"),
        ("beganegrond_signal", True, "75", "75", "unavailable"),
        ("eerste_etage_signal", True, "100", "100", "100"),
        ("zolder_signal", True, None, "25", "25"),
        ("corner_signal", True, "unavailable", "unavailable", "unavailable"),
    ],
)
async def test_sensor_updates(
    hass: HomeAssistant,
    mock_k1_connector: dict[AsyncMock],
    mock_entry: ConfigEntry,
    sensor: str,
    enable: bool,
    state1: Any,
    state2: Any,
    state3: Any,
) -> None:
    """Test we can setup and tear down platforms dynamically."""

    async def async_enable_entity(entity_id: str):
        """Enable disabled by default sensor."""
        entity_registry = er.async_get(hass)
        entry = entity_registry.async_get(entity_id)
        if entry and enable:
            entity_registry.async_update_entity(entity_id, disabled_by=None)
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RELOAD,
                {},
                blocking=False,
            )

    # Updated status holds device info for device [1,2,4]
    updated_status_data = copy.deepcopy(MOCK_DEVICE_STATUS_DATA)
    # Initial status holds device info for device [1,2]
    initial_status_data = copy.deepcopy(updated_status_data)
    initial_status_data.pop(4)

    # setup integration with 2 devices
    mock_k1_connector["result"].return_value = initial_status_data
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    await async_enable_entity(f"sensor.{sensor}")
    await hass.async_block_till_done()
    if state1 is None:
        assert hass.states.get(f"sensor.{sensor}") is None
    else:
        assert hass.states.get(f"sensor.{sensor}").state == state1

    # Simulate a dynamic discovery update resulting in 3 devices
    mock_k1_connector["result"].return_value = updated_status_data
    time = dt.now() + timedelta(seconds=30)
    async_fire_time_changed(hass, time)
    # await coordinator.async_request_refresh()
    await hass.async_block_till_done()
    await async_enable_entity(f"sensor.{sensor}")
    await hass.async_block_till_done()

    assert hass.states.get(f"sensor.{sensor}").state == state2

    # Remove device 1 from api data, entity should appear offline with an unknown state
    updated_status_data.pop(1)

    mock_k1_connector["result"].return_value = updated_status_data
    time = time + timedelta(seconds=30)
    async_fire_time_changed(hass, time)
    await hass.async_block_till_done()

    assert hass.states.get(f"sensor.{sensor}").state == state3
