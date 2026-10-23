"""Tests for the Electra Smart binary sensors."""

from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_advance_to_next_poll

FILTER_ENTITY_ID = "binary_sensor.living_room_filter_cleaning_required"
INDOOR_COIL_FAULT_ENTITY_ID = "binary_sensor.living_room_indoor_coil_sensor_fault"
RETURN_AIR_FAULT_ENTITY_ID = "binary_sensor.living_room_return_air_sensor_fault"


async def test_binary_sensors(
    hass: HomeAssistant,
    mock_api: Mock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
) -> None:
    """Test the binary sensors of an AC."""
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.electrasmart.ElectraAPI", return_value=mock_api
        ),
        patch(
            "homeassistant.components.electrasmart.PLATFORMS",
            [Platform.BINARY_SENSOR],
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("setup_integration")
async def test_filter_clean_required(
    hass: HomeAssistant,
    mock_device: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The filter reminder follows the device."""
    assert hass.states.get(FILTER_ENTITY_ID).state == "off"

    mock_device.get_filter_clean_required = Mock(return_value=True)

    await async_advance_to_next_poll(hass, freezer)

    assert hass.states.get(FILTER_ENTITY_ID).state == "on"


@pytest.mark.parametrize(
    ("measurement", "expected"), [("NORM", "off"), ("NORMAL", "off"), ("BAD", "on")]
)
@pytest.mark.usefixtures("setup_integration")
async def test_sensor_fault_flag(
    hass: HomeAssistant,
    mock_device: Mock,
    freezer: FrozenDateTimeFactory,
    measurement: str,
    expected: str,
) -> None:
    """The healthy spelling of a sensor fault flag is not the same on every AC."""
    mock_device.measurements["I_BAD_ICT"] = measurement
    mock_device.measurements["I_BAD_RAT"] = measurement

    await async_advance_to_next_poll(hass, freezer)

    assert hass.states.get(INDOOR_COIL_FAULT_ENTITY_ID).state == expected
    assert hass.states.get(RETURN_AIR_FAULT_ENTITY_ID).state == expected


@pytest.mark.usefixtures("setup_integration")
async def test_missing_sensor_fault_flag_is_not_a_fault(
    hass: HomeAssistant,
    mock_device: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An AC that stops reporting a fault flag is not reported as faulty."""
    mock_device.measurements.pop("I_BAD_ICT")

    await async_advance_to_next_poll(hass, freezer)

    assert hass.states.get(INDOOR_COIL_FAULT_ENTITY_ID).state == "off"


async def test_unit_without_the_reminder_flag_gets_no_filter_entity(
    hass: HomeAssistant,
    mock_api: Mock,
    mock_device: Mock,
    config_entry: MockConfigEntry,
) -> None:
    """A unit that does not report CLEAR_FILT gets no filter reminder entity."""
    mock_device.get_filter_clean_required = Mock(return_value=None)
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.electrasmart.ElectraAPI", return_value=mock_api
        ),
        patch(
            "homeassistant.components.electrasmart.PLATFORMS",
            [Platform.BINARY_SENSOR],
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)
    assert FILTER_ENTITY_ID not in entity_ids
    # The fault flags this unit does report are still there.
    assert INDOOR_COIL_FAULT_ENTITY_ID in entity_ids


@pytest.mark.usefixtures("setup_integration")
async def test_reminder_that_stops_being_reported_is_unknown(
    hass: HomeAssistant,
    mock_device: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A reminder the unit stops reporting is unknown, not a cleared reminder."""
    mock_device.get_filter_clean_required = Mock(return_value=True)

    await async_advance_to_next_poll(hass, freezer)

    assert hass.states.get(FILTER_ENTITY_ID).state == "on"

    mock_device.get_filter_clean_required = Mock(return_value=None)

    await async_advance_to_next_poll(hass, freezer)

    assert hass.states.get(FILTER_ENTITY_ID).state == STATE_UNKNOWN


async def test_fault_flag_reported_after_setup_gets_its_entity(
    hass: HomeAssistant,
    mock_api: Mock,
    mock_device: Mock,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
) -> None:
    """A unit that only reports a flag later gets the binary sensor then."""
    mock_device.measurements.pop("I_BAD_ICT")
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.electrasmart.ElectraAPI", return_value=mock_api
        ),
        patch(
            "homeassistant.components.electrasmart.PLATFORMS",
            [Platform.BINARY_SENSOR],
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert INDOOR_COIL_FAULT_ENTITY_ID not in hass.states.async_entity_ids(
        BINARY_SENSOR_DOMAIN
    )

    mock_device.measurements["I_BAD_ICT"] = "NORM"

    await async_advance_to_next_poll(hass, freezer)

    assert hass.states.get(INDOOR_COIL_FAULT_ENTITY_ID).state == "off"


@pytest.mark.usefixtures("setup_integration")
async def test_disconnected_ac_makes_the_binary_sensors_unavailable(
    hass: HomeAssistant,
    mock_device: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An AC that stopped reporting does not expose its cached flags."""
    mock_device.is_disconnected = Mock(return_value=True)

    await async_advance_to_next_poll(hass, freezer)

    assert hass.states.get(FILTER_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(INDOOR_COIL_FAULT_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_device.is_disconnected = Mock(return_value=False)

    await async_advance_to_next_poll(hass, freezer)

    assert hass.states.get(FILTER_ENTITY_ID).state == "off"
