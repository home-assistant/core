"""Test sensor of Airly integration."""

from collections.abc import Generator
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from airly.exceptions import AirlyError
from airly.measurements import Measurement
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.airly.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("mock_airly_client")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the sensor."""
    await init_integration(hass, mock_config_entry)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


@pytest.mark.parametrize(
    "exception",
    [
        AirlyError(HTTPStatus.NOT_FOUND, {"message": "Not found"}),
        TimeoutError(),
    ],
)
async def test_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airly_client: MagicMock,
    exception: Exception,
) -> None:
    """Ensure that we mark the entities unavailable correctly.

    Test when service is offline.
    """
    await init_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "68.35"

    mock_airly_client.create_measurements_session_point.return_value.update.side_effect = exception
    future = utcnow() + timedelta(minutes=60)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_airly_client.create_measurements_session_point.return_value.update.side_effect = None
    future = utcnow() + timedelta(minutes=120)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "68.35"


async def test_manual_update_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airly_client: MagicMock,
) -> None:
    """Test manual update entity via service homeassistant/update_entity."""
    await init_integration(hass, mock_config_entry)

    measurements = mock_airly_client.create_measurements_session_point.return_value
    call_count = measurements.update.call_count
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["sensor.home_humidity"]},
        blocking=True,
    )

    assert measurements.update.call_count == call_count + 1


@pytest.mark.parametrize(
    ("entity_id", "key", "value"),
    [
        ("sensor.home_temperature", "TEMPERATURE", "14.37"),
        ("sensor.home_pm2_5", "PM25", "4.37"),
    ],
)
async def test_missing_measurement(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airly_client: MagicMock,
    mock_airly_measurements: Measurement,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    entity_id: str,
    key: str,
    value: str,
) -> None:
    """Test the entity state is unknown when the API omits its measurement."""
    await init_integration(hass, mock_config_entry)

    measurements = mock_airly_client.create_measurements_session_point.return_value
    measurements.current = Measurement(
        {
            **mock_airly_measurements,
            "values": [
                item
                for item in mock_airly_measurements["values"]
                if item["name"] != key
            ],
        }
    )
    freezer.tick(timedelta(minutes=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert "Unexpected error updating listener" not in caplog.text

    measurements.current = mock_airly_measurements
    freezer.tick(timedelta(minutes=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == value


async def test_zero_value_creates_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airly_client: MagicMock,
    mock_airly_measurements: Measurement,
) -> None:
    """Test an entity is created for a measurement with a value of zero."""
    measurements = mock_airly_client.create_measurements_session_point.return_value
    measurements.current = Measurement(
        {**mock_airly_measurements, "values": [{"name": "SO2", "value": 0}]}
    )

    await init_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.home_sulphur_dioxide")
    assert state
    assert state.state == "0"


async def test_missing_standard(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airly_client: MagicMock,
    mock_airly_measurements: Measurement,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the entity keeps its value when the API omits the pollutant standard."""
    await init_integration(hass, mock_config_entry)

    measurements = mock_airly_client.create_measurements_session_point.return_value
    measurements.current = Measurement(
        {
            **mock_airly_measurements,
            "standards": [
                item
                for item in mock_airly_measurements["standards"]
                if item["pollutant"] != "PM25"
            ],
        }
    )
    freezer.tick(timedelta(minutes=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_pm2_5")
    assert state
    assert state.state == "4.37"
    assert state.attributes["limit"] is None
    assert state.attributes["percent"] is None
