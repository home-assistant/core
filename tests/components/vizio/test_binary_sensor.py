"""Tests for the Vizio binary sensor platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from vizaio import ChargingStatus

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

CHARGING_ENTITY_ID = "binary_sensor.vizio_charging"


@pytest.fixture(autouse=True)
def binary_sensor_only() -> Generator[None]:
    """Only set up the binary sensor platform."""
    with patch(
        "homeassistant.components.vizio.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        yield


@pytest.mark.usefixtures("vizio_connect", "vizio_update", "vizio_battery")
async def test_binary_sensor_entity_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_crave_config_entry: MockConfigEntry,
) -> None:
    """Test the charging binary sensor is created for a Crave device."""
    await setup_integration(hass, mock_crave_config_entry)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_crave_config_entry.entry_id
    )


@pytest.mark.usefixtures("vizio_connect", "vizio_update", "vizio_battery")
@pytest.mark.parametrize(
    ("charging_status", "expected_state"),
    [
        (ChargingStatus.CHARGING, STATE_ON),
        (ChargingStatus.NOT_CHARGING, STATE_OFF),
        # A full battery is no longer drawing charge, so this is off. The
        # battery level sensor is what tells the user it is full.
        (ChargingStatus.FULLY_CHARGED, STATE_OFF),
    ],
)
async def test_charging_states(
    hass: HomeAssistant,
    mock_crave_config_entry: MockConfigEntry,
    charging_status: ChargingStatus,
    expected_state: str,
) -> None:
    """Test each charging status maps to the right binary state."""
    with patch(
        "homeassistant.components.vizio.Vizio.get_charging_status",
        return_value=charging_status,
    ):
        await setup_integration(hass, mock_crave_config_entry)

    assert hass.states.get(CHARGING_ENTITY_ID).state == expected_state


@pytest.mark.usefixtures("vizio_connect", "vizio_update", "vizio_battery")
async def test_charging_unavailable_data(
    hass: HomeAssistant,
    mock_crave_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the charging binary sensor reports unknown when the device is off."""
    await setup_integration(hass, mock_crave_config_entry)

    with patch(
        "homeassistant.components.vizio.Vizio.get_power_state",
        return_value=False,
    ):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get(CHARGING_ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_no_binary_sensor_for_soundbar(
    hass: HomeAssistant, mock_speaker_config_entry: MockConfigEntry
) -> None:
    """Test no charging binary sensor is created for a soundbar."""
    await setup_integration(hass, mock_speaker_config_entry)

    assert hass.states.get(CHARGING_ENTITY_ID) is None
