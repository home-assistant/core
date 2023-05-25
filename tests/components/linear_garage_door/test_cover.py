"""Test Linear Garage Door cover."""

from datetime import datetime as dt, timedelta
from unittest.mock import patch

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.components.linear_garage_door.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
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
    assert hass.states.get("cover.test_garage_1").state == STATE_OPEN
    assert hass.states.get("cover.test_garage_2").state == STATE_CLOSED


async def test_open_cover(hass: HomeAssistant) -> None:
    """Test that opening the cover works as intended."""

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.linear_garage_door.cover.Linear.operate_device"
    ) as operate_device:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: "cover.test_garage_1"},
            blocking=True,
        )

    assert operate_device.call_count == 0

    with patch(
        "homeassistant.components.linear_garage_door.cover.Linear.login",
        return_value=True,
    ), patch(
        "homeassistant.components.linear_garage_door.cover.Linear.operate_device",
        return_value=None,
    ) as operate_device, patch(
        "homeassistant.components.linear_garage_door.cover.Linear.close",
        return_value=True,
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: "cover.test_garage_2"},
            blocking=True,
        )

    assert operate_device.call_count == 1
    with patch(
        "homeassistant.components.linear_garage_door.cover.Linear.login",
        return_value=True,
    ), patch(
        "homeassistant.components.linear_garage_door.cover.Linear.get_devices",
        return_value=[
            {"id": "test1", "name": "Test Garage 1", "subdevices": ["GDO", "Light"]},
            {"id": "test2", "name": "Test Garage 2", "subdevices": ["GDO", "Light"]},
        ],
    ), patch(
        "homeassistant.components.linear_garage_door.cover.Linear.get_device_state",
        side_effect=lambda id: {
            "test1": {
                "GDO": {"Open_B": "true", "Open_P": "100"},
                "Light": {"On_B": "true", "On_P": "100"},
            },
            "test2": {
                "GDO": {"Open_B": "false", "Opening_P": "0"},
                "Light": {"On_B": "false", "On_P": "0"},
            },
        }[id],
    ), patch(
        "homeassistant.components.linear_garage_door.cover.Linear.close",
        return_value=True,
    ):
        async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()

    assert hass.states.get("cover.test_garage_2").state == STATE_OPENING


async def test_close_cover(hass: HomeAssistant) -> None:
    """Test that closing the cover works as intended."""

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.linear_garage_door.cover.Linear.operate_device"
    ) as operate_device:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: "cover.test_garage_2"},
            blocking=True,
        )

    assert operate_device.call_count == 0

    with patch(
        "homeassistant.components.linear_garage_door.cover.Linear.login",
        return_value=True,
    ), patch(
        "homeassistant.components.linear_garage_door.cover.Linear.operate_device",
        return_value=None,
    ) as operate_device, patch(
        "homeassistant.components.linear_garage_door.cover.Linear.close",
        return_value=True,
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: "cover.test_garage_1"},
            blocking=True,
        )

    assert operate_device.call_count == 1
    with patch(
        "homeassistant.components.linear_garage_door.cover.Linear.login",
        return_value=True,
    ), patch(
        "homeassistant.components.linear_garage_door.cover.Linear.get_devices",
        return_value=[
            {"id": "test1", "name": "Test Garage 1", "subdevices": ["GDO", "Light"]},
            {"id": "test2", "name": "Test Garage 2", "subdevices": ["GDO", "Light"]},
        ],
    ), patch(
        "homeassistant.components.linear_garage_door.cover.Linear.get_device_state",
        side_effect=lambda id: {
            "test1": {
                "GDO": {"Open_B": "true", "Closing_P": "100"},
                "Light": {"On_B": "true", "On_P": "100"},
            },
            "test2": {
                "GDO": {"Open_B": "false", "Open_P": "0"},
                "Light": {"On_B": "false", "On_P": "0"},
            },
        }[id],
    ), patch(
        "homeassistant.components.linear_garage_door.cover.Linear.close",
        return_value=True,
    ):
        async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()

    assert hass.states.get("cover.test_garage_1").state == STATE_CLOSING
