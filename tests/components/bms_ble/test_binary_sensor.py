"""Test the BLE Battery Management System integration binary sensor definition."""

from datetime import timedelta
from typing import Final

from aiobmsble import BMSMode, BMSSample
from habluetooth import BluetoothServiceInfoBleak
import pytest

from homeassistant.components.bms_ble.const import BINARY_SENSORS, UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State
import homeassistant.util.dt as dt_util

from .conftest import mock_config, mock_devinfo_min, mock_update_full

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import inject_bluetooth_service_info_bleak

SEN_PREFIX: Final[str] = "binary_sensor.config_test_dummy_bms"


@pytest.mark.usefixtures(
    "enable_bluetooth", "patch_default_bleak_client", "patch_entity_enabled_default"
)  # enable bluetooth, patch bleak client and enable all sensors
async def test_update(
    monkeypatch: pytest.MonkeyPatch,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Test binary sensor value updates through coordinator."""

    async def patch_async_update(_self) -> BMSSample:
        """Patch async ble device from address to return a given value."""
        return {
            "voltage": 17.0,
            "current": 0,
            "problem": True,
            "balancer": 0x31,
            "chrg_mosfet": False,
            "dischrg_mosfet": True,
            "heater": True,
            "problem_code": 0x73,
            "battery_mode": BMSMode.ABSORPTION,
        }

    bms_class: Final[str] = "aiobmsble.bms.dummy_bms.BMS"
    monkeypatch.setattr(f"{bms_class}.device_info", mock_devinfo_min)
    monkeypatch.setattr(f"{bms_class}.async_update", mock_update_full)

    config: MockConfigEntry = mock_config()
    config.add_to_hass(hass)

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    assert config in hass.config_entries.async_entries()
    assert config.state is ConfigEntryState.LOADED
    assert len(hass.states.async_all(["binary_sensor"])) == BINARY_SENSORS
    for sensor, attribute, ref_state in (
        ("charging", "battery_mode", STATE_ON),
        ("problem", "problem_code", STATE_OFF),
    ):
        state: State | None = hass.states.get(f"{SEN_PREFIX}_{sensor}")
        assert state is not None
        assert state.state == ref_state
        assert not state.attributes.get(attribute)

    monkeypatch.setattr(f"{bms_class}.async_update", patch_async_update)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=UPDATE_INTERVAL))
    await hass.async_block_till_done()

    for sensor, attribute, ref_state, ref_value in (
        ("charging", "battery_mode", STATE_OFF, "absorption"),
        ("problem", "problem_code", STATE_ON, 0x73),
        ("charge_mosfet", "", STATE_OFF, None),
        ("discharge_mosfet", "", STATE_ON, None),
        ("heater", "", STATE_ON, None),
        ("balancer", "cells", STATE_ON, 0x31),
    ):
        state = hass.states.get(f"{SEN_PREFIX}_{sensor}")
        assert state is not None, f"no state for sensor {sensor}"
        assert state.state == ref_state
        if attribute:
            assert state.attributes.get(attribute) == ref_value
