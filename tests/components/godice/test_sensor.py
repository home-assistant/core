"""Test godice integration components."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import godice
import pytest

from homeassistant.components.godice.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.godice.dice import DiceProxy
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

    def store_rolled_number_cb(cb):
        nonlocal rolled_number_cb
        rolled_number_cb = cb

    color = godice.Color.BLUE
    battery_level = 99
    rolled_number = 4

    fake_dice.subscribe_number_notification.side_effect = store_rolled_number_cb
    fake_dice.get_battery_level.return_value = battery_level
    fake_dice.get_color.return_value = color

    with patch(
        "homeassistant.components.godice.create_dice",
        return_value=fake_dice,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

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

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_connection_proxy(hass: HomeAssistant, fake_dice) -> None:
    """Verify DiceProxy establishes connection and notifies when connection is lost."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=GODICE_DEVICE_SERVICE_INFO.address,
        data={
            "name": GODICE_DEVICE_SERVICE_INFO.name,
            "address": GODICE_DEVICE_SERVICE_INFO.address,
        },
    )
    config_entry.add_to_hass(hass)
    proxy = DiceProxy(hass, config_entry)

    _rolled_number_cb = None
    _rolled_number = None

    async def store_rolled_number_cb(cb):
        nonlocal _rolled_number_cb
        _rolled_number_cb = cb

    async def rolled_number_cb(val, _rollstate):
        nonlocal _rolled_number
        _rolled_number = val

    mock = AsyncMock()
    with patch(
        "godice.create",
        return_value=fake_dice,
    ), patch(
        "homeassistant.components.godice.dice.establish_connection",
        return_value=mock,
    ), patch(
        "homeassistant.components.godice.dice.close_stale_connections",
        return_value=mock,
    ):
        color = godice.Color.BLUE
        battery_level = 40
        rolled_number = 5
        fake_dice.get_color.return_value = color
        fake_dice.get_battery_level.return_value = battery_level
        fake_dice.subscribe_number_notification.side_effect = store_rolled_number_cb

        assert (await proxy.get_color()) is None
        assert (await proxy.get_battery_level()) is None

        disconnect_cb = AsyncMock()
        await proxy.connect(disconnect_cb)
        assert (await proxy.get_color()) == color
        assert (await proxy.get_battery_level()) == battery_level
        await proxy.subscribe_number_notification(rolled_number_cb)
        await _rolled_number_cb(rolled_number, None)
        assert _rolled_number == rolled_number

        await proxy.disconnect()
        # emulate disconnect event generated by Bleak when disconnected
        proxy._on_disconnected_handler(None)
        disconnect_cb.assert_called_once_with(None, True)
        assert (await proxy.get_color()) is None
        assert (await proxy.get_battery_level()) is None

        disconnect_cb = AsyncMock()
        await proxy.connect(disconnect_cb)
        assert (await proxy.get_color()) == color
        assert (await proxy.get_battery_level()) == battery_level
        await proxy.subscribe_number_notification(rolled_number_cb)
        await _rolled_number_cb(rolled_number, None)
        assert _rolled_number == rolled_number

        # emulate disconnect event generated by Bleak when disconnected
        proxy._on_disconnected_handler(None)
        assert (await proxy.get_color()) is None
        assert (await proxy.get_battery_level()) is None
        disconnect_cb.assert_called_once_with(None, False)
