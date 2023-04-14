"""Test Linear Garage Door light."""

from datetime import datetime as dt, timedelta
from unittest.mock import patch

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.linear_garage_door.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_BRIGHTNESS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .util import async_init_integration

from tests.common import async_fire_time_changed


async def test_data(hass: HomeAssistant) -> None:
    """Test that data gets parsed and returned appropriately."""

    await async_init_integration(hass)

    assert hass.data[DOMAIN]
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state == ConfigEntryState.LOADED
    assert hass.states.get("light.test_garage_1_light").state == STATE_ON
    assert hass.states.get("light.test_garage_2_light").state == STATE_OFF


async def test_turn_on(hass: HomeAssistant) -> None:
    """Test that turning on the light works as intended."""

    await async_init_integration(hass)

    with patch("linear_garage_door.Linear.login", return_value=True), patch(
        "linear_garage_door.Linear.operate_device", return_value=None
    ) as operate_device, patch("linear_garage_door.Linear.close", return_value=True):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.test_garage_2_light"},
            blocking=True,
        )

    assert operate_device.call_count == 1
    with patch("linear_garage_door.Linear.login", return_value=True), patch(
        "linear_garage_door.Linear.get_devices",
        return_value=[
            {"id": "test1", "name": "Test Garage 1", "subdevices": ["GDO", "Light"]},
            {"id": "test2", "name": "Test Garage 2", "subdevices": ["GDO", "Light"]},
        ],
    ), patch(
        "linear_garage_door.Linear.get_device_state",
        side_effect=lambda id: {
            "test1": {
                "GDO": {"Open_B": "true", "Open_P": "100"},
                "Light": {"On_B": "true", "On_P": "100"},
            },
            "test2": {
                "GDO": {"Open_B": "false", "Open_P": "0"},
                "Light": {"On_B": "true", "On_P": "100"},
            },
        }[id],
    ), patch(
        "linear_garage_door.Linear.close", return_value=True
    ):
        async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()

    assert hass.states.get("light.test_garage_2_light").state == STATE_ON


async def test_turn_on_with_brightness(hass: HomeAssistant) -> None:
    """Test that turning on the light works as intended."""

    await async_init_integration(hass)

    with patch("linear_garage_door.Linear.login", return_value=True), patch(
        "linear_garage_door.Linear.operate_device", return_value=None
    ) as operate_device, patch("linear_garage_door.Linear.close", return_value=True):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.test_garage_2_light", CONF_BRIGHTNESS: 50},
            blocking=True,
        )

    assert operate_device.call_count == 1
    with patch("linear_garage_door.Linear.login", return_value=True), patch(
        "linear_garage_door.Linear.get_devices",
        return_value=[
            {"id": "test1", "name": "Test Garage 1", "subdevices": ["GDO", "Light"]},
            {"id": "test2", "name": "Test Garage 2", "subdevices": ["GDO", "Light"]},
        ],
    ), patch(
        "linear_garage_door.Linear.get_device_state",
        side_effect=lambda id: {
            "test1": {
                "GDO": {"Open_B": "true", "Open_P": "100"},
                "Light": {"On_B": "true", "On_P": "100"},
            },
            "test2": {
                "GDO": {"Open_B": "false", "Open_P": "0"},
                "Light": {"On_B": "true", "On_P": "50"},
            },
        }[id],
    ), patch(
        "linear_garage_door.Linear.close", return_value=True
    ):
        async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()

    assert hass.states.get("light.test_garage_2_light").state == STATE_ON
    assert (
        hass.states.get("light.test_garage_2_light").attributes.get("brightness")
        == 127.5
    )


async def test_close_cover(hass: HomeAssistant) -> None:
    """Test that turning off the light works as intended."""

    await async_init_integration(hass)

    with patch("linear_garage_door.Linear.login", return_value=True), patch(
        "linear_garage_door.Linear.operate_device", return_value=None
    ) as operate_device, patch("linear_garage_door.Linear.close", return_value=True):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.test_garage_1_light"},
            blocking=True,
        )

    assert operate_device.call_count == 1
    with patch("linear_garage_door.Linear.login", return_value=True), patch(
        "linear_garage_door.Linear.get_devices",
        return_value=[
            {"id": "test1", "name": "Test Garage 1", "subdevices": ["GDO", "Light"]},
            {"id": "test2", "name": "Test Garage 2", "subdevices": ["GDO", "Light"]},
        ],
    ), patch(
        "linear_garage_door.Linear.get_device_state",
        side_effect=lambda id: {
            "test1": {
                "GDO": {"Open_B": "true", "Closing_P": "100"},
                "Light": {"On_B": "false", "On_P": "0"},
            },
            "test2": {
                "GDO": {"Open_B": "false", "Open_P": "0"},
                "Light": {"On_B": "false", "On_P": "0"},
            },
        }[id],
    ), patch(
        "linear_garage_door.Linear.close", return_value=True
    ):
        async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()

    assert hass.states.get("light.test_garage_1_light").state == STATE_OFF
