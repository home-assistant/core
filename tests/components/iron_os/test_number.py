"""Tests for the IronOS number platform."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pynecil import CharSetting, CommunicationError, TempUnit
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.iron_os.const import (
    MAX_TEMP_F,
    MIN_BOOST_TEMP_F,
    MIN_TEMP_F,
)
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
async def number_only() -> AsyncGenerator[None]:
    """Enable only the number platform."""
    with patch(
        "homeassistant.components.iron_os.PLATFORMS",
        [Platform.NUMBER],
    ):
        yield


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_pynecil", "ble_device"
)
async def test_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the IronOS number platform states."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "min_value", "max_value"),
    [
        ("number.pinecil_setpoint_temperature", MIN_TEMP_F, MAX_TEMP_F),
        ("number.pinecil_boost_temperature", MIN_BOOST_TEMP_F, MAX_TEMP_F),
        ("number.pinecil_long_press_temperature_step", 5, 90),
        ("number.pinecil_short_press_temperature_step", 1, 50),
        ("number.pinecil_sleep_temperature", MIN_TEMP_F, MAX_TEMP_F),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "ble_device")
async def test_state_fahrenheit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_pynecil: AsyncMock,
    entity_id: str,
    min_value: int,
    max_value: int,
) -> None:
    """Test with temp unit set to fahrenheit."""

    mock_pynecil.get_settings.return_value["temp_unit"] = TempUnit.FAHRENHEIT

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None

    assert state.attributes["min"] == min_value
    assert state.attributes["max"] == max_value


@pytest.mark.parametrize(
    ("entity_id", "characteristic", "value", "expected_value"),
    [
        (
            "number.pinecil_setpoint_temperature",
            CharSetting.SETPOINT_TEMP,
            300,
            300,
        ),
        (
            "number.pinecil_boost_temperature",
            CharSetting.BOOST_TEMP,
            420,
            420,
        ),
        (
            "number.pinecil_calibration_offset",
            CharSetting.CALIBRATION_OFFSET,
            600,
            600,
        ),
        (
            "number.pinecil_display_brightness",
            CharSetting.DISPLAY_BRIGHTNESS,
            3,
            3,
        ),
        (
            "number.pinecil_hall_effect_sensitivity",
            CharSetting.HALL_SENSITIVITY,
            7,
            7,
        ),
        (
            "number.pinecil_keep_awake_pulse_delay",
            CharSetting.KEEP_AWAKE_PULSE_DELAY,
            10.0,
            4,
        ),
        (
            "number.pinecil_keep_awake_pulse_duration",
            CharSetting.KEEP_AWAKE_PULSE_DURATION,
            500,
            2,
        ),
        (
            "number.pinecil_keep_awake_pulse_intensity",
            CharSetting.KEEP_AWAKE_PULSE_POWER,
            0.5,
            0.5,
        ),
        (
            "number.pinecil_long_press_temperature_step",
            CharSetting.TEMP_INCREMENT_LONG,
            10,
            10,
        ),
        (
            "number.pinecil_min_voltage_per_cell",
            CharSetting.MIN_VOLTAGE_PER_CELL,
            3.3,
            3.3,
        ),
        ("number.pinecil_motion_sensitivity", CharSetting.ACCEL_SENSITIVITY, 7, 7),
        (
            "number.pinecil_power_delivery_timeout",
            CharSetting.PD_NEGOTIATION_TIMEOUT,
            2.0,
            2.0,
        ),
        ("number.pinecil_power_limit", CharSetting.POWER_LIMIT, 120, 120),
        ("number.pinecil_quick_charge_voltage", CharSetting.QC_IDEAL_VOLTAGE, 9.0, 9.0),
        (
            "number.pinecil_short_press_temperature_step",
            CharSetting.TEMP_INCREMENT_SHORT,
            1,
            1,
        ),
        ("number.pinecil_shutdown_timeout", CharSetting.SHUTDOWN_TIME, 10, 10),
        ("number.pinecil_sleep_temperature", CharSetting.SLEEP_TEMP, 150, 150),
        ("number.pinecil_sleep_timeout", CharSetting.SLEEP_TIMEOUT, 5, 5),
        ("number.pinecil_voltage_divider", CharSetting.VOLTAGE_DIV, 600, 600),
        (
            "number.pinecil_hall_sensor_sleep_timeout",
            CharSetting.HALL_SLEEP_TIME,
            60,
            60,
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "ble_device")
async def test_set_value(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pynecil: AsyncMock,
    entity_id: str,
    characteristic: CharSetting,
    value: float,
    expected_value: float,
) -> None:
    """Test the IronOS number platform set value service."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: value},
        target={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert len(mock_pynecil.write.mock_calls) == 1
    mock_pynecil.write.assert_called_once_with(characteristic, expected_value)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "ble_device")
async def test_set_value_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pynecil: AsyncMock,
) -> None:
    """Test the IronOS number platform set value service with exception."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_pynecil.write.side_effect = CommunicationError

    with pytest.raises(
        ServiceValidationError,
        match="Failed to submit setting to device, try again later",
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            service_data={ATTR_VALUE: 300},
            target={ATTR_ENTITY_ID: "number.pinecil_setpoint_temperature"},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "ble_device")
async def test_boost_temp_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pynecil: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test boost temp input is unavailable when off."""
    mock_pynecil.get_settings.return_value["boost_temp"] = 0

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("number.pinecil_boost_temperature"))
    assert state.state == STATE_UNAVAILABLE
