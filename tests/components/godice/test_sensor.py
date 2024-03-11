"""Test godice integration components."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import godice
import pytest

from homeassistant.components.godice.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.godice.dice import ConnectionState, DiceProxy
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import GODICE_DEVICE_SERVICE_INFO

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def fake_dice():
    """Mock a real GoDice."""
    return AsyncMock(DiceProxy)


async def test_sensor_reading(hass: HomeAssistant, fake_dice) -> None:
    """Verify data provided by GoDice is stored in HA state."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=GODICE_DEVICE_SERVICE_INFO.address,
        data={
            "name": GODICE_DEVICE_SERVICE_INFO.name,
            "address": GODICE_DEVICE_SERVICE_INFO.address,
        },
    )
    config_entry.add_to_hass(hass)

    rolled_number_cb = None
    conn_state_cb = None

    def store_rolled_number_cb(cb):
        nonlocal rolled_number_cb
        rolled_number_cb = cb

    def store_conn_state_cb(cb):
        nonlocal conn_state_cb
        conn_state_cb = cb

    color = godice.Color.BLUE
    battery_level = 99
    rolled_number = 4

    fake_dice.subscribe_number_notification.side_effect = store_rolled_number_cb
    fake_dice.subscribe_connection_notification.side_effect = store_conn_state_cb
    fake_dice.get_battery_level.return_value = battery_level
    fake_dice.get_color.return_value = color

    with patch(
        "homeassistant.components.godice.create_dice",
        return_value=fake_dice,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await conn_state_cb(ConnectionState.CONNECTED)
    await hass.async_block_till_done()

    connection = hass.states.get(f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_connection")
    assert connection is not None
    assert connection.state == "CONNECTED"

    color_sensor = hass.states.get(f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_color")
    assert color_sensor is not None
    assert color_sensor.state == color.name

    await rolled_number_cb(rolled_number, None)
    await hass.async_block_till_done()

    rolled_number_sensor = hass.states.get(
        f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_rolled_number"
    )
    assert rolled_number_sensor is not None
    assert rolled_number_sensor.state == str(rolled_number)

    async_fire_time_changed(
        hass, dt_util.utcnow() + SCAN_INTERVAL + timedelta(seconds=10)
    )
    await hass.async_block_till_done()

    battery_level_sensor = hass.states.get(
        f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_battery_level"
    )
    assert battery_level_sensor is not None
    assert battery_level_sensor.state == str(battery_level)

    rolled_number = 2
    battery_level = 30
    fake_dice.get_battery_level.return_value = battery_level

    await rolled_number_cb(rolled_number, None)
    async_fire_time_changed(
        hass, dt_util.utcnow() + SCAN_INTERVAL + timedelta(seconds=10)
    )
    await hass.async_block_till_done()

    rolled_number_sensor = hass.states.get(
        f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_rolled_number"
    )
    assert rolled_number_sensor is not None
    assert rolled_number_sensor.state == str(rolled_number)

    battery_level_sensor = hass.states.get(
        f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_battery_level"
    )
    assert battery_level_sensor is not None
    assert battery_level_sensor.state == str(battery_level)

    await conn_state_cb(ConnectionState.CONNECTING)
    await hass.async_block_till_done()

    connection = hass.states.get(f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_connection")
    assert connection is not None
    assert connection.state == "CONNECTING"

    color_sensor = hass.states.get(f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_color")
    assert color_sensor is not None
    assert color_sensor.state == color.name

    rolled_number_sensor = hass.states.get(
        f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_rolled_number"
    )
    assert rolled_number_sensor is not None
    assert rolled_number_sensor.state == str(rolled_number)

    battery_level_sensor = hass.states.get(
        f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_battery_level"
    )
    assert battery_level_sensor is not None
    assert battery_level_sensor.state == str(battery_level)

    await conn_state_cb(ConnectionState.DISCONNECTED)
    await hass.async_block_till_done()

    connection = hass.states.get(f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_connection")
    assert connection is not None
    assert connection.state == "DISCONNECTED"

    color_sensor = hass.states.get(f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_color")
    assert color_sensor is not None
    assert color_sensor.state == color.name

    rolled_number_sensor = hass.states.get(
        f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_rolled_number"
    )
    assert rolled_number_sensor is not None
    assert rolled_number_sensor.state == str(rolled_number)

    battery_level_sensor = hass.states.get(
        f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_battery_level"
    )
    assert battery_level_sensor is not None
    assert battery_level_sensor.state == str(battery_level)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_dice_proxy(hass: HomeAssistant, fake_dice) -> None:
    """Verify DiceProxy returns cached values when device connection lost."""
    conn_handler = AsyncMock()
    proxy = DiceProxy(conn_handler)

    _rolled_number_cb = None
    _conn_state = None
    _rolled_number = None

    async def store_rolled_number_cb(cb):
        nonlocal _rolled_number_cb
        _rolled_number_cb = cb

    async def conn_state_cb(val):
        nonlocal _conn_state
        _conn_state = val

    async def rolled_number_cb(val, _rollstate):
        nonlocal _rolled_number
        _rolled_number = val

    fake_dice.subscribe_number_notification.side_effect = store_rolled_number_cb

    await proxy.subscribe_connection_notification(conn_state_cb)
    await proxy.subscribe_number_notification(rolled_number_cb)

    with patch(
        "godice.create",
        return_value=fake_dice,
    ):
        color = godice.Color.BLUE
        battery_level = 40
        fake_dice.get_color.return_value = color
        fake_dice.get_battery_level.return_value = battery_level

        await proxy.on_connected(None)
        assert _conn_state == ConnectionState.CONNECTED
        assert (await proxy.get_color()) == color
        assert (await proxy.get_battery_level()) == battery_level
        await _rolled_number_cb(2, None)
        assert _rolled_number == 2

        await proxy.on_reconnecting()
        old_battery_level = battery_level
        new_battery_level = 99
        fake_dice.get_battery_level.return_value = new_battery_level
        assert _conn_state == ConnectionState.CONNECTING
        assert (await proxy.get_color()) == color
        assert (await proxy.get_battery_level()) == old_battery_level

        await proxy.on_connected(None)
        assert _conn_state == ConnectionState.CONNECTED
        assert (await proxy.get_color()) == color
        assert (await proxy.get_battery_level()) == new_battery_level
        await _rolled_number_cb(5, None)
        assert _rolled_number == 5

        await proxy.on_disconnected()
        assert _conn_state == ConnectionState.DISCONNECTED
        assert (await proxy.get_color()) == color
        assert (await proxy.get_battery_level()) == new_battery_level
