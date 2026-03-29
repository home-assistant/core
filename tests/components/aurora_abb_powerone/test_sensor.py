"""Test the Aurora ABB PowerOne Solar PV sensors."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.aurora_abb_powerone.aurora_client import (
    AuroraClientError,
    AuroraClientTimeoutError,
    AuroraInverterData,
)
from homeassistant.components.aurora_abb_powerone.const import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntryDisabler

from tests.common import MockConfigEntry, async_fire_time_changed

DEVICE_NAME = "Solar Inverter"


def _make_inverter_data(**overrides: object) -> AuroraInverterData:
    """Create an AuroraInverterData with sensible defaults, optionally overridden."""
    defaults = {
        "grid_voltage": 235.9,
        "grid_current": 2.8,
        "instantaneouspower": 45.7,
        "grid_frequency": 50.8,
        "i_leak_dcdc": 1.2345,
        "i_leak_inverter": 2.3456,
        "power_in_1": 12.3,
        "power_in_2": 23.5,
        "temp": 9.9,
        "voltage_in_1": 123.5,
        "current_in_1": 1.0,
        "voltage_in_2": 234.6,
        "current_in_2": 1.2,
        "r_iso": 0.1234,
        "totalenergy": 12.35,
        "alarm": "No alarm",
    }
    defaults.update(overrides)
    return AuroraInverterData(**defaults)


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor values from inverter data."""
    mock_client = MagicMock()
    mock_client.try_connect_and_fetch_data.return_value = _make_inverter_data()

    with patch(
        "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraClient.from_serial",
        return_value=mock_client,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    power = hass.states.get(
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_power_output"
    )
    assert power is not None
    assert power.state == "45.7"

    temperature = hass.states.get(
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_temperature"
    )
    assert temperature is not None
    assert temperature.state == "9.9"

    energy = hass.states.get(
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_total_energy"
    )
    assert energy is not None
    assert energy.state == "12.35"

    # Test disabled-by-default sensors exist in registry but not in state machine
    disabled_sensors = [
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_grid_voltage",
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_grid_current",
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_grid_frequency",
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_dc_dc_leak_current",
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_inverter_leak_current",
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_string_1_power",
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_string_2_power",
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_string_1_voltage",
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_string_1_current",
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_string_2_voltage",
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_string_2_current",
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_isolation_resistance",
    ]
    for entity_id in disabled_sensors:
        assert not hass.states.get(entity_id), f"Expected {entity_id} to be disabled"
        entry = entity_registry.async_get(entity_id)
        assert entry is not None, f"Entity registry entry missing for {entity_id}"
        assert entry.disabled
        assert entry.disabled_by is RegistryEntryDisabler.INTEGRATION

        # Re-enable so we can check values after reload
        entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)

    # Reload integration to apply the now-enabled sensors
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraClient.from_serial",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    expected_values = [
        (f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_grid_voltage", "235.9"),
        (f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_grid_current", "2.8"),
        (f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_grid_frequency", "50.8"),
        (
            f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_dc_dc_leak_current",
            "1.2345",
        ),
        (
            f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_inverter_leak_current",
            "2.3456",
        ),
        (f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_string_1_power", "12.3"),
        (f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_string_2_power", "23.5"),
        (f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_string_1_voltage", "123.5"),
        (f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_string_1_current", "1.0"),
        (f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_string_2_voltage", "234.6"),
        (f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_string_2_current", "1.2"),
        (
            f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_isolation_resistance",
            "0.1234",
        ),
    ]
    for entity_id, expected_value in expected_values:
        item = hass.states.get(entity_id)
        assert item is not None, f"State missing for {entity_id}"
        assert item.state == expected_value


async def test_sensor_dark(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that darkness (timeout / no response) is handled correctly."""
    mock_client = MagicMock()
    mock_client.try_connect_and_fetch_data.return_value = _make_inverter_data()

    with patch(
        "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraClient.from_serial",
        return_value=mock_client,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    power = hass.states.get(
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_power_output"
    )
    assert power is not None
    assert power.state == "45.7"

    # Simulate sunset – inverter stops responding
    mock_client.try_connect_and_fetch_data.side_effect = AuroraClientTimeoutError
    freezer.tick(SCAN_INTERVAL * 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    energy = hass.states.get(
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_total_energy"
    )
    assert energy is not None
    assert energy.state == "unknown"

    # Simulate sunrise – inverter responds again
    mock_client.try_connect_and_fetch_data.side_effect = None
    mock_client.try_connect_and_fetch_data.return_value = _make_inverter_data()
    freezer.tick(SCAN_INTERVAL * 4)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    power = hass.states.get(
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_power_output"
    )
    assert power is not None
    assert power.state == "45.7"


async def test_sensor_unknown_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a generic communication error marks sensors unavailable."""
    mock_client = MagicMock()
    mock_client.try_connect_and_fetch_data.return_value = _make_inverter_data()

    with patch(
        "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraClient.from_serial",
        return_value=mock_client,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_client.try_connect_and_fetch_data.side_effect = AuroraClientError(
        "another error"
    )
    freezer.tick(SCAN_INTERVAL * 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    power = hass.states.get(
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_power_output"
    )
    assert power is not None
    assert power.state == "unavailable"
