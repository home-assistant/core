"""Tests for the Electra Smart sensors."""

from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_advance_to_next_poll

WIFI_SIGNAL_ENTITY_ID = "sensor.living_room_wi_fi_signal"
INDOOR_COIL_TEMPERATURE_ENTITY_ID = "sensor.living_room_indoor_coil_temperature"
OUTDOOR_COIL_TEMPERATURE_ENTITY_ID = "sensor.living_room_outdoor_coil_temperature"


async def test_sensors(
    hass: HomeAssistant,
    mock_api: Mock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
) -> None:
    """Test the sensors of an AC."""
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.electrasmart.ElectraAPI", return_value=mock_api
        ),
        patch("homeassistant.components.electrasmart.PLATFORMS", [Platform.SENSOR]),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("setup_integration")
async def test_sensors_report_the_measurements(hass: HomeAssistant) -> None:
    """The sensors report the telemetry of the device."""
    assert hass.states.get(WIFI_SIGNAL_ENTITY_ID).state == "-53"
    assert hass.states.get(INDOOR_COIL_TEMPERATURE_ENTITY_ID).state == "21"
    assert hass.states.get(OUTDOOR_COIL_TEMPERATURE_ENTITY_ID).state == "25"


async def test_measurements_are_not_exposed_when_the_ac_does_not_report_them(
    hass: HomeAssistant,
    mock_api: Mock,
    mock_device: Mock,
    config_entry: MockConfigEntry,
) -> None:
    """An AC that reports no telemetry gets no sensors."""
    mock_device.measurements = {}
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.electrasmart.ElectraAPI", return_value=mock_api
        ),
        patch("homeassistant.components.electrasmart.PLATFORMS", [Platform.SENSOR]),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.async_entity_ids(SENSOR_DOMAIN) == []


@pytest.mark.usefixtures("setup_integration")
async def test_unreadable_measurement_is_unknown(
    hass: HomeAssistant,
    mock_device: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A measurement that is not a number leaves the sensor unknown."""
    mock_device.measurements["WI_FI_RSSI"] = "N/A"

    await async_advance_to_next_poll(hass, freezer)

    assert hass.states.get(WIFI_SIGNAL_ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.usefixtures("setup_integration")
async def test_disconnected_ac_makes_the_sensors_unavailable(
    hass: HomeAssistant,
    mock_device: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An AC that stopped reporting does not expose its cached measurements."""
    mock_device.is_disconnected = Mock(return_value=True)

    await async_advance_to_next_poll(hass, freezer)

    assert hass.states.get(WIFI_SIGNAL_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(INDOOR_COIL_TEMPERATURE_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_device.is_disconnected = Mock(return_value=False)

    await async_advance_to_next_poll(hass, freezer)

    assert hass.states.get(WIFI_SIGNAL_ENTITY_ID).state == "-53"
