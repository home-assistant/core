"""Test godice integration components."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import godice

from homeassistant.components.godice.const import SCAN_INTERVAL
from homeassistant.components.godice.sensor import (
    BATTERY_SENSOR_DESCR,
    COLOR_SENSOR_DESCR,
    ROLLED_NUMBER_SENSOR_DESCR,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import GODICE_DEVICE_SERVICE_INFO

from tests.common import async_fire_time_changed


async def test_sensor_reading(hass: HomeAssistant, config_entry, fake_dice) -> None:
    """Verify data provided by GoDice is stored in HA state."""
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

    with (
        patch(
            "godice.create",
            return_value=fake_dice,
        ),
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=GODICE_DEVICE_SERVICE_INFO,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    fake_dice.pulse_led.assert_called_once()

    color_sensor = hass.states.get(
        f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_{COLOR_SENSOR_DESCR.key}"
    )
    assert color_sensor is not None
    assert color_sensor.state == color.name

    await rolled_number_cb(rolled_number, None)
    await hass.async_block_till_done()

    rolled_number_sensor = hass.states.get(
        f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_{ROLLED_NUMBER_SENSOR_DESCR.key}"
    )
    assert rolled_number_sensor is not None
    assert rolled_number_sensor.state == str(rolled_number)

    async_fire_time_changed(
        hass, dt_util.utcnow() + SCAN_INTERVAL + timedelta(seconds=10)
    )
    await hass.async_block_till_done()

    battery_level_sensor = hass.states.get(
        f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_{BATTERY_SENSOR_DESCR.key}"
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
        f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_{ROLLED_NUMBER_SENSOR_DESCR.key}"
    )
    assert rolled_number_sensor is not None
    assert rolled_number_sensor.state == str(rolled_number)

    battery_level_sensor = hass.states.get(
        f"sensor.{GODICE_DEVICE_SERVICE_INFO.name}_{BATTERY_SENSOR_DESCR.key}"
    )
    assert battery_level_sensor is not None
    assert battery_level_sensor.state == str(battery_level)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_reloading_on_connection_lost(
    hass: HomeAssistant, config_entry, fake_dice
) -> None:
    """Verify integration gets reloaded when connection to GoDice is lost."""
    with (
        patch(
            "godice.create",
            return_value=fake_dice,
        ) as dice_constructor,
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload",
            return_value=None,
        ) as mock_reload,
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=GODICE_DEVICE_SERVICE_INFO,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        disconnect_cb = dice_constructor.call_args.kwargs["disconnected_callback"]

        # no reloading when disconnected by request
        config_entry.runtime_data.disconnected_by_request_flag = True
        disconnect_cb(None)
        await hass.async_block_till_done()
        mock_reload.assert_not_called()

        # reloading when connection is lost
        config_entry.runtime_data.disconnected_by_request_flag = False
        disconnect_cb(None)
        await hass.async_block_till_done()
        mock_reload.assert_called()
