"""Test for the SmartThings sensors platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability
from pysmartthings.models import HealthStatus
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    set_attribute_value,
    setup_integration,
    snapshot_smartthings_entities,
    trigger_health_update,
    trigger_update,
)


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.SENSOR)


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.theater_ac_office_granit_temperature").state == "25"

    await trigger_update(
        hass,
        devices,
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        Capability.TEMPERATURE_MEASUREMENT,
        Attribute.TEMPERATURE,
        20,
    )

    assert hass.states.get("sensor.theater_ac_office_granit_temperature").state == "20"


@pytest.mark.parametrize("device_fixture", ["multipurpose_sensor"])
async def test_three_axis_none_value(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test three axis coordinate sensors handle a None value."""
    set_attribute_value(devices, Capability.THREE_AXIS, Attribute.THREE_AXIS, None)

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.theater_deck_door_x_coordinate").state == (
        STATE_UNKNOWN
    )
    assert hass.states.get("sensor.theater_deck_door_y_coordinate").state == (
        STATE_UNKNOWN
    )
    assert hass.states.get("sensor.theater_deck_door_z_coordinate").state == (
        STATE_UNKNOWN
    )


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.theater_ac_office_granit_temperature").state == "25"

    await trigger_health_update(
        hass, devices, "96a5ef74-5832-a84b-f1f7-ca799957065d", HealthStatus.OFFLINE
    )

    assert (
        hass.states.get("sensor.theater_ac_office_granit_temperature").state
        == STATE_UNAVAILABLE
    )

    await trigger_health_update(
        hass, devices, "96a5ef74-5832-a84b-f1f7-ca799957065d", HealthStatus.ONLINE
    )

    assert hass.states.get("sensor.theater_ac_office_granit_temperature").state == "25"


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert (
        hass.states.get("sensor.theater_ac_office_granit_temperature").state
        == STATE_UNAVAILABLE
    )


@pytest.mark.parametrize("device_fixture", ["da_vc_stick_01001"])
@pytest.mark.parametrize(
    ("reported_state", "expected_state"),
    [
        ("usingVacuum", "using_vacuum"),
        ("emptyingDustbin", "emptying_dustbin"),
        ("UVCleaning", "uv_cleaning"),
        ("UVPaused", "uv_paused"),
        ("ready", "ready"),
    ],
)
async def test_stick_cleaner_operating_state_is_mapped(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    reported_state: str,
    expected_state: str,
) -> None:
    """Test the stick cleaner states are mapped onto the entity options."""
    await setup_integration(hass, mock_config_entry)

    await trigger_update(
        hass,
        devices,
        "e1f93c0c-6fe0-c65a-a314-c8f7b163c86b",
        Capability.SAMSUNG_CE_STICK_CLEANER_STATUS,
        Attribute.OPERATING_STATE,
        reported_state,
    )

    assert (state := hass.states.get("sensor.stick_vacuum"))
    assert state.state == expected_state


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_partial_power_consumption_report(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a partial report with a negative energy value does not crash."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.theater_washer_energy").state == "352.8"
    assert hass.states.get("sensor.theater_washer_power").state == "0"

    await trigger_update(
        hass,
        devices,
        "f984b91d-f250-9d42-3436-33f09a422a47",
        Capability.POWER_CONSUMPTION_REPORT,
        Attribute.POWER_CONSUMPTION,
        {"energy": -1},
    )

    assert hass.states.get("sensor.theater_washer_energy").state == STATE_UNKNOWN
    assert hass.states.get("sensor.theater_washer_power").state == STATE_UNKNOWN
    assert hass.states.get("sensor.theater_washer_energy_saved").state == STATE_UNKNOWN


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_negative_power_consumption_values(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test negative values are unknown only for always increasing sensors."""
    await setup_integration(hass, mock_config_entry)

    await trigger_update(
        hass,
        devices,
        "f984b91d-f250-9d42-3436-33f09a422a47",
        Capability.POWER_CONSUMPTION_REPORT,
        Attribute.POWER_CONSUMPTION,
        {
            "energy": 352800,
            "power": 0,
            "energySaved": -5,
            "deltaEnergy": -200,
            "powerEnergy": -300,
        },
    )

    assert hass.states.get("sensor.theater_washer_energy_saved").state == STATE_UNKNOWN
    assert hass.states.get("sensor.theater_washer_energy_difference").state == "-0.2"
    assert hass.states.get("sensor.theater_washer_power_energy").state == "-0.3"
