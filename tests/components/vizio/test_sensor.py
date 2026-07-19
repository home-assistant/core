"""Tests for the Vizio sensor platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from vizaio import ChargingStatus

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

BATTERY_ENTITY_ID = "sensor.vizio_battery"
CHARGING_ENTITY_ID = "sensor.vizio_charging_status"


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Only set up the sensor platform."""
    with patch(
        "homeassistant.components.vizio.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


@pytest.fixture(name="vizio_battery")
def vizio_battery_fixture() -> Generator[None]:
    """Mock battery state for a Crave device."""
    with (
        patch(
            "homeassistant.components.vizio.Vizio.get_battery_level",
            return_value=80,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_charging_status",
            return_value=ChargingStatus.CHARGING,
        ),
    ):
        yield


@pytest.mark.usefixtures("vizio_connect", "vizio_update", "vizio_battery")
async def test_sensor_entity_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_crave_config_entry: MockConfigEntry,
) -> None:
    """Test battery sensors are created for a Crave device."""
    await setup_integration(hass, mock_crave_config_entry)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_crave_config_entry.entry_id
    )


@pytest.mark.usefixtures("vizio_connect", "vizio_update", "vizio_battery")
async def test_sensor_values(
    hass: HomeAssistant, mock_crave_config_entry: MockConfigEntry
) -> None:
    """Test battery sensor values."""
    await setup_integration(hass, mock_crave_config_entry)

    assert hass.states.get(BATTERY_ENTITY_ID).state == "80"
    assert hass.states.get(CHARGING_ENTITY_ID).state == "charging"


@pytest.mark.usefixtures("vizio_connect", "vizio_update", "vizio_battery")
async def test_sensor_values_unavailable_data(
    hass: HomeAssistant,
    mock_crave_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test battery sensors report unknown when the device is off."""
    await setup_integration(hass, mock_crave_config_entry)

    with patch(
        "homeassistant.components.vizio.Vizio.get_power_state",
        return_value=False,
    ):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get(BATTERY_ENTITY_ID).state == STATE_UNKNOWN
    assert hass.states.get(CHARGING_ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_no_sensors_for_soundbar(
    hass: HomeAssistant, mock_speaker_config_entry: MockConfigEntry
) -> None:
    """Test no battery sensors are created for a soundbar."""
    await setup_integration(hass, mock_speaker_config_entry)

    assert hass.states.get(BATTERY_ENTITY_ID) is None
    assert hass.states.get(CHARGING_ENTITY_ID) is None
