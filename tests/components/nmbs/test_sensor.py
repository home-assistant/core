"""Test the NMBS sensor platform."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import logging
from unittest.mock import AsyncMock

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
from mashumaro.exceptions import MissingField
from pyrail import PyRailError
from pyrail.models import ConnectionsApiResponse, LiveboardApiResponse
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
)

from homeassistant.components.nmbs.const import (
    CONF_EXCLUDE_VIAS,
    CONF_STATION_FROM,
    CONF_STATION_TO,
    DOMAIN,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_SHOW_ON_MAP,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import STATION_FROM, STATION_TO

FROZEN_TIME = "2025-10-09T12:00:00+00:00"
UPDATE_INTERVAL = timedelta(seconds=60)

CONNECTION_UNIQUE_ID = f"nmbs_connection_{STATION_FROM}_{STATION_TO}"
LIVEBOARD_FROM_UNIQUE_ID = f"nmbs_live_{STATION_FROM}_{STATION_FROM}_{STATION_TO}"
LIVEBOARD_TO_UNIQUE_ID = f"nmbs_live_{STATION_TO}_{STATION_FROM}_{STATION_TO}"


def _get_entity_id(entity_registry: er.EntityRegistry, unique_id: str) -> str:
    """Return the entity_id for a sensor unique_id."""
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def _setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up a config entry."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _enable_liveboards(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entry: MockConfigEntry
) -> None:
    """Enable the liveboard sensors and reload the entry."""
    for unique_id in (LIVEBOARD_FROM_UNIQUE_ID, LIVEBOARD_TO_UNIQUE_ID):
        entity_registry.async_update_entity(
            _get_entity_id(entity_registry, unique_id), disabled_by=None
        )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


def _liveboard_api_failure() -> LiveboardApiResponse | None:
    """Simulate a liveboard request that returns no data."""
    return None


def _liveboard_timeout() -> LiveboardApiResponse | None:
    """Simulate a liveboard request that times out."""
    raise TimeoutError


def _liveboard_decoding_error() -> LiveboardApiResponse | None:
    """Simulate a liveboard response that fails to decode."""
    raise ValueError("Unexpected response schema")


def _liveboard_missing_field() -> LiveboardApiResponse | None:
    """Simulate a liveboard response that misses a required field."""
    raise MissingField("delay", "datetime", "LiveboardDeparture")


@freeze_time(FROZEN_TIME)
async def test_sensors_setup(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensors are set up with their legacy unique IDs and names."""
    await _setup_entry(hass, mock_config_entry)

    for unique_id in (
        CONNECTION_UNIQUE_ID,
        LIVEBOARD_FROM_UNIQUE_ID,
        LIVEBOARD_TO_UNIQUE_ID,
    ):
        assert entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)

    state = hass.states.get(_get_entity_id(entity_registry, CONNECTION_UNIQUE_ID))
    assert state is not None
    assert (
        state.name
        == "Train from Brussel-Noord/Bruxelles-Nord to Brussel-Zuid/Bruxelles-Midi"
    )

    for unique_id in (LIVEBOARD_FROM_UNIQUE_ID, LIVEBOARD_TO_UNIQUE_ID):
        registry_entry = entity_registry.async_get(
            _get_entity_id(entity_registry, unique_id)
        )
        assert registry_entry is not None
        assert registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@freeze_time(FROZEN_TIME)
async def test_connection_sensor(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the connection sensor state and attributes for a connection with a via."""
    await _setup_entry(hass, mock_config_entry)

    state = hass.states.get(_get_entity_id(entity_registry, CONNECTION_UNIQUE_ID))
    assert state is not None
    assert state.state == "20"
    attrs = state.attributes
    assert attrs["destination"] == "Brussel-Zuid/Bruxelles-Midi"
    assert attrs["direction"] == "Blankenberge"
    assert attrs["platform_arriving"] == "9"
    assert attrs["platform_departing"] == "5"
    assert attrs["vehicle_id"] == "BE.NMBS.IC1832"
    assert attrs["canceled"] is False
    assert attrs["departure"] == "In 10 minutes"
    assert attrs["departure_minutes"] == 10
    assert attrs["departure_time"] == datetime(2025, 10, 9, 12, 10, tzinfo=UTC)
    assert attrs["delay_seconds"] == 600
    assert attrs["delay"] == "10 minutes"
    assert attrs["delay_minutes"] == 10
    assert attrs["via"] == "Brussel-Centraal/Bruxelles-Central"
    assert attrs["via_arrival_platform"] == "12"
    assert attrs["via_transfer_platform"] == "12"
    assert attrs["via_transfer_time"] == 5
    assert attrs["icon"] == "mdi:alert-octagon"
    assert attrs["unit_of_measurement"] == "min"
    assert "latitude" not in attrs


@freeze_time(FROZEN_TIME)
async def test_connection_sensor_exclude_vias(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the connection sensor skips connections with a via when excluded."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Train from Brussel-Noord/Bruxelles-Nord to Brussel-Zuid/Bruxelles-Midi",
        data={
            CONF_STATION_FROM: STATION_FROM,
            CONF_STATION_TO: STATION_TO,
            CONF_EXCLUDE_VIAS: True,
        },
        unique_id=f"{STATION_FROM}_{STATION_TO}_excl_vias",
    )
    await _setup_entry(hass, entry)

    state = hass.states.get(
        _get_entity_id(entity_registry, f"{CONNECTION_UNIQUE_ID}_excl_vias")
    )
    assert state is not None
    assert state.state == "10"
    attrs = state.attributes
    assert attrs["departure"] == "In 30 minutes"
    assert attrs["departure_minutes"] == 30
    assert attrs["departure_time"] is not None
    assert attrs["delay_seconds"] == 0
    assert attrs["delay"] == "0 minutes"
    assert attrs["delay_minutes"] == 0
    assert attrs["icon"] == "mdi:train"
    assert "via" not in attrs


@freeze_time(FROZEN_TIME)
async def test_connection_sensor_show_on_map(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the connection sensor exposes station coordinates for the map."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Train from Brussel-Noord/Bruxelles-Nord to Brussel-Zuid/Bruxelles-Midi",
        data={
            CONF_STATION_FROM: STATION_FROM,
            CONF_STATION_TO: STATION_TO,
        },
        options={CONF_SHOW_ON_MAP: True},
        minor_version=2,
        unique_id=f"{STATION_FROM}_{STATION_TO}_map",
    )
    await _setup_entry(hass, entry)

    state = hass.states.get(_get_entity_id(entity_registry, CONNECTION_UNIQUE_ID))
    assert state is not None
    assert state.attributes["latitude"] == 50.859663
    assert state.attributes["longitude"] == 4.360846


@freeze_time(FROZEN_TIME)
async def test_connection_sensor_keeps_custom_name(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the connection sensor keeps the name stored in an existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My train to work",
        data={
            CONF_STATION_FROM: STATION_FROM,
            CONF_STATION_TO: STATION_TO,
            CONF_NAME: "My train to work",
        },
        unique_id=f"{STATION_FROM}_{STATION_TO}_named",
    )
    await _setup_entry(hass, entry)

    state = hass.states.get(_get_entity_id(entity_registry, CONNECTION_UNIQUE_ID))
    assert state is not None
    assert state.name == "My train to work"


@freeze_time(FROZEN_TIME)
async def test_connection_sensor_canceled(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the connection sensor attributes for a canceled departure."""
    connections = ConnectionsApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "connections.json", DOMAIN)
    )
    connections.connections[1].departure.canceled = True
    mock_nmbs_client.get_connections.return_value = connections
    await _setup_entry(hass, mock_config_entry)

    state = hass.states.get(_get_entity_id(entity_registry, CONNECTION_UNIQUE_ID))
    assert state is not None
    assert state.attributes["canceled"] is True
    assert state.attributes["departure"] is None
    assert state.attributes["departure_time"] is not None
    assert state.attributes["departure_minutes"] is None


@freeze_time(FROZEN_TIME)
async def test_connection_sensor_no_upcoming_connection(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the connection sensor is unknown when no connection is upcoming."""
    connections = ConnectionsApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "connections.json", DOMAIN)
    )
    for connection in connections.connections:
        connection.departure.left = True
    mock_nmbs_client.get_connections.return_value = connections
    await _setup_entry(hass, mock_config_entry)

    state = hass.states.get(_get_entity_id(entity_registry, CONNECTION_UNIQUE_ID))
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["icon"] == "mdi:train"


@freeze_time(FROZEN_TIME)
async def test_liveboard_sensors(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the liveboard sensors show the next departure."""
    await _setup_entry(hass, mock_config_entry)
    await _enable_liveboards(hass, entity_registry, mock_config_entry)

    from_state = hass.states.get(
        _get_entity_id(entity_registry, LIVEBOARD_FROM_UNIQUE_ID)
    )
    assert from_state is not None
    assert from_state.name == "Trains in Brussel-Noord/Bruxelles-Nord"
    assert from_state.state == "Track 3 - Blankenberge"
    attrs = from_state.attributes
    assert attrs["monitored_station"] == "Brussel-Noord/Bruxelles-Nord"
    assert attrs["departure"] == "In 5 minutes"
    assert attrs["departure_minutes"] == 5
    assert attrs["departure_time"] is not None
    assert attrs["extra_train"] is False
    assert attrs["vehicle_id"] == "BE.NMBS.IC1832"
    assert attrs["delay_seconds"] == 600
    assert attrs["delay"] == "10 minutes"
    assert attrs["delay_minutes"] == 10
    assert attrs["icon"] == "mdi:alert-octagon"

    to_state = hass.states.get(_get_entity_id(entity_registry, LIVEBOARD_TO_UNIQUE_ID))
    assert to_state is not None
    assert to_state.name == "Trains in Brussel-Zuid/Bruxelles-Midi"
    assert to_state.state == "Track 7 - Gent-Sint-Pieters"
    to_attrs = to_state.attributes
    assert to_attrs["monitored_station"] == "Brussel-Zuid/Bruxelles-Midi"
    assert to_attrs["departure"] == "In 5 minutes"
    assert to_attrs["departure_minutes"] == 5
    assert to_attrs["extra_train"] is False
    assert to_attrs["vehicle_id"] == "BE.NMBS.IC3536"
    assert "delay_seconds" not in to_attrs
    assert "delay" not in to_attrs
    assert "delay_minutes" not in to_attrs
    assert to_attrs["icon"] == "mdi:train"


@freeze_time(FROZEN_TIME)
async def test_liveboard_sensor_no_departures(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the liveboard sensor is unknown when there are no departures."""
    liveboard = LiveboardApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "liveboard.json", DOMAIN)
    )
    liveboard.departures = []
    mock_nmbs_client.get_liveboard.side_effect = lambda station_id: liveboard
    await _setup_entry(hass, mock_config_entry)
    await _enable_liveboards(hass, entity_registry, mock_config_entry)

    state = hass.states.get(_get_entity_id(entity_registry, LIVEBOARD_FROM_UNIQUE_ID))
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["icon"] == "mdi:train"


@freeze_time(FROZEN_TIME)
async def test_liveboard_sensor_no_delay(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the liveboard sensor attributes when the next departure has no delay."""
    liveboard = LiveboardApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "liveboard.json", DOMAIN)
    )
    liveboard.departures[0].delay = 0
    mock_nmbs_client.get_liveboard.side_effect = lambda station_id: liveboard
    await _setup_entry(hass, mock_config_entry)
    await _enable_liveboards(hass, entity_registry, mock_config_entry)

    state = hass.states.get(_get_entity_id(entity_registry, LIVEBOARD_FROM_UNIQUE_ID))
    assert state is not None
    attrs = state.attributes
    assert attrs["icon"] == "mdi:train"
    assert "delay_seconds" not in attrs
    assert "delay" not in attrs
    assert "delay_minutes" not in attrs


@pytest.mark.parametrize(
    "destination_liveboard_result",
    [
        pytest.param(_liveboard_api_failure, id="api_failure"),
        pytest.param(_liveboard_timeout, id="timeout"),
        pytest.param(_liveboard_decoding_error, id="decoding_error"),
        pytest.param(_liveboard_missing_field, id="missing_field"),
    ],
)
async def test_liveboard_failure_only_affects_its_sensor(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    destination_liveboard_result: Callable[[], LiveboardApiResponse | None],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed liveboard only affects its own sensor and recovers."""
    freezer.move_to(FROZEN_TIME)
    await _setup_entry(hass, mock_config_entry)

    liveboards = {
        STATION_FROM: LiveboardApiResponse.from_dict(
            await async_load_json_object_fixture(hass, "liveboard.json", DOMAIN)
        ),
    }
    liveboard_results = {
        STATION_FROM: lambda: liveboards[STATION_FROM],
        STATION_TO: destination_liveboard_result,
    }
    mock_nmbs_client.get_liveboard.side_effect = lambda station_id: liveboard_results[
        station_id
    ]()
    await _enable_liveboards(hass, entity_registry, mock_config_entry)

    connection_state = hass.states.get(
        _get_entity_id(entity_registry, CONNECTION_UNIQUE_ID)
    )
    assert connection_state is not None
    assert connection_state.state == "20"

    from_state = hass.states.get(
        _get_entity_id(entity_registry, LIVEBOARD_FROM_UNIQUE_ID)
    )
    assert from_state is not None
    assert from_state.state == "Track 3 - Blankenberge"

    to_state = hass.states.get(_get_entity_id(entity_registry, LIVEBOARD_TO_UNIQUE_ID))
    assert to_state is not None
    assert to_state.state == STATE_UNAVAILABLE

    liveboards[STATION_TO] = LiveboardApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "liveboard_zuid.json", DOMAIN)
    )
    mock_nmbs_client.get_liveboard.side_effect = lambda station_id: liveboards[
        station_id
    ]
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    to_state = hass.states.get(_get_entity_id(entity_registry, LIVEBOARD_TO_UNIQUE_ID))
    assert to_state is not None
    assert to_state.state == "Track 7 - Gent-Sint-Pieters"


async def test_disabled_liveboards_are_not_fetched(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the coordinator does not fetch liveboards of disabled entities."""
    await _setup_entry(hass, mock_config_entry)

    assert mock_nmbs_client.get_connections.call_count == 1
    assert mock_nmbs_client.get_liveboard.call_count == 0


async def test_enabled_liveboard_is_fetched(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test only the liveboard of an enabled entity is fetched."""
    await _setup_entry(hass, mock_config_entry)
    assert mock_nmbs_client.get_liveboard.call_count == 0

    entity_registry.async_update_entity(
        _get_entity_id(entity_registry, LIVEBOARD_FROM_UNIQUE_ID), disabled_by=None
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_nmbs_client.get_liveboard.call_count == 1
    mock_nmbs_client.get_liveboard.assert_called_once_with(station_id=STATION_FROM)


@pytest.mark.parametrize(
    "connection_side_effect",
    [
        pytest.param(PyRailError("API unavailable"), id="api_failure"),
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(ValueError("Unexpected response schema"), id="decoding_error"),
        pytest.param(
            MissingField("delay", "datetime", "ConnectionDetails"), id="missing_field"
        ),
    ],
)
async def test_connection_failure_only_affects_its_sensor(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    connection_side_effect: Exception | type[Exception],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed connection only affects the connection sensor and recovers."""
    freezer.move_to(FROZEN_TIME)
    await _setup_entry(hass, mock_config_entry)
    await _enable_liveboards(hass, entity_registry, mock_config_entry)

    from_id = _get_entity_id(entity_registry, LIVEBOARD_FROM_UNIQUE_ID)
    from_state = hass.states.get(from_id)
    assert from_state is not None
    assert from_state.state == "Track 3 - Blankenberge"

    mock_nmbs_client.get_connections.side_effect = connection_side_effect
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    connection_state = hass.states.get(
        _get_entity_id(entity_registry, CONNECTION_UNIQUE_ID)
    )
    assert connection_state is not None
    assert connection_state.state == STATE_UNAVAILABLE

    from_state = hass.states.get(from_id)
    assert from_state is not None
    assert from_state.state == "Track 3 - Blankenberge"

    mock_nmbs_client.get_connections.side_effect = None
    mock_nmbs_client.get_connections.return_value = ConnectionsApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "connections.json", DOMAIN)
    )
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    connection_state = hass.states.get(
        _get_entity_id(entity_registry, CONNECTION_UNIQUE_ID)
    )
    assert connection_state is not None
    assert connection_state.state == "20"


async def test_connection_feed_logs_failure_and_recovery_once(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test connection feed transitions are logged once."""
    await _setup_entry(hass, mock_config_entry)
    mock_nmbs_client.get_connections.side_effect = PyRailError("API unavailable")

    with caplog.at_level(logging.WARNING):
        freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        sum(
            "Unable to fetch the connection" in record.message
            for record in caplog.records
        )
        == 1
    )

    mock_nmbs_client.get_connections.side_effect = None
    with caplog.at_level(logging.INFO):
        freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert sum("Recovered feed" in record.message for record in caplog.records) == 1


async def test_disabled_connection_is_not_fetched(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the coordinator stops fetching connections when the entity is disabled."""
    await _setup_entry(hass, mock_config_entry)
    assert mock_nmbs_client.get_connections.call_count == 1

    entity_registry.async_update_entity(
        _get_entity_id(entity_registry, CONNECTION_UNIQUE_ID),
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_nmbs_client.get_connections.call_count == 1
    assert mock_nmbs_client.get_liveboard.call_count == 0


async def test_removed_connection_entity_is_fetched(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the coordinator fetches connections when the entity was removed."""
    await _setup_entry(hass, mock_config_entry)
    assert mock_nmbs_client.get_connections.call_count == 1

    entity_registry.async_remove(_get_entity_id(entity_registry, CONNECTION_UNIQUE_ID))
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_nmbs_client.get_connections.call_count == 2


async def test_unexpected_error_fails_the_refresh(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an unexpected error makes all sensors unavailable."""
    freezer.move_to(FROZEN_TIME)
    await _setup_entry(hass, mock_config_entry)
    await _enable_liveboards(hass, entity_registry, mock_config_entry)

    mock_nmbs_client.get_connections.side_effect = RuntimeError("Unexpected")
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for unique_id in (
        CONNECTION_UNIQUE_ID,
        LIVEBOARD_FROM_UNIQUE_ID,
        LIVEBOARD_TO_UNIQUE_ID,
    ):
        state = hass.states.get(_get_entity_id(entity_registry, unique_id))
        assert state is not None
        assert state.state == STATE_UNAVAILABLE


async def test_connection_sensor_keeps_data_when_api_is_not_modified(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the connection sensor keeps data when the API returns 304."""
    freezer.move_to(FROZEN_TIME)
    await _setup_entry(hass, mock_config_entry)
    connection_id = _get_entity_id(entity_registry, CONNECTION_UNIQUE_ID)
    assert mock_nmbs_client.get_connections.call_count == 1

    mock_nmbs_client.get_connections.return_value = None
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_nmbs_client.get_connections.call_count == 2
    state = hass.states.get(connection_id)
    assert state is not None
    assert state.state == "20"
    assert state.attributes["departure_minutes"] == 9


async def test_departure_minutes_decrease_with_unchanged_data(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test minute counters update even when the API returns unchanged data."""
    freezer.move_to(FROZEN_TIME)
    await _setup_entry(hass, mock_config_entry)

    connection_id = _get_entity_id(entity_registry, CONNECTION_UNIQUE_ID)
    state = hass.states.get(connection_id)
    assert state is not None
    assert state.attributes["departure"] == "In 10 minutes"
    assert state.attributes["departure_time"] is not None
    assert state.attributes["departure_minutes"] == 10

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(connection_id)
    assert state is not None
    assert state.attributes["departure"] == "In 9 minutes"
    assert state.attributes["departure_time"] is not None
    assert state.attributes["departure_minutes"] == 9


@freeze_time(FROZEN_TIME)
async def test_liveboard_sensor_alerts_on_short_delay(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the liveboard sensor shows the alert icon for a delay under a minute."""
    liveboard = LiveboardApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "liveboard.json", DOMAIN)
    )
    liveboard.departures[0].delay = 20
    mock_nmbs_client.get_liveboard.side_effect = lambda station_id: liveboard
    await _setup_entry(hass, mock_config_entry)
    await _enable_liveboards(hass, entity_registry, mock_config_entry)

    state = hass.states.get(_get_entity_id(entity_registry, LIVEBOARD_FROM_UNIQUE_ID))
    assert state is not None
    assert state.attributes["icon"] == "mdi:alert-octagon"
    assert state.attributes["delay_seconds"] == 20
    assert "delay" not in state.attributes
    assert "delay_minutes" not in state.attributes


@freeze_time(FROZEN_TIME)
async def test_connection_sensor_keeps_map_location_without_connection(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the connection sensor stays on the map when no train is found."""
    connections = ConnectionsApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "connections.json", DOMAIN)
    )
    for connection in connections.connections:
        connection.departure.left = True
    mock_nmbs_client.get_connections.return_value = connections
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Train from Brussel-Noord/Bruxelles-Nord to Brussel-Zuid/Bruxelles-Midi",
        data={
            CONF_STATION_FROM: STATION_FROM,
            CONF_STATION_TO: STATION_TO,
        },
        options={CONF_SHOW_ON_MAP: True},
        minor_version=2,
        unique_id=f"{STATION_FROM}_{STATION_TO}",
    )
    await _setup_entry(hass, entry)

    state = hass.states.get(_get_entity_id(entity_registry, CONNECTION_UNIQUE_ID))
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["latitude"] == 50.859663
    assert state.attributes["longitude"] == 4.360846
    assert "destination" not in state.attributes


async def test_liveboard_recovery_logged_only_when_available(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a liveboard logs recovery only once its sensor is available again."""
    freezer.move_to(FROZEN_TIME)
    await _setup_entry(hass, mock_config_entry)
    await _enable_liveboards(hass, entity_registry, mock_config_entry)
    liveboard_id = _get_entity_id(entity_registry, LIVEBOARD_FROM_UNIQUE_ID)
    liveboard = LiveboardApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "liveboard.json", DOMAIN)
    )
    empty_liveboard = LiveboardApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "liveboard.json", DOMAIN)
    )
    empty_liveboard.departures = None

    mock_nmbs_client.get_liveboard.side_effect = TimeoutError
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_nmbs_client.get_liveboard.side_effect = lambda station_id: empty_liveboard
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(liveboard_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert "Recovered feed" not in caplog.text

    mock_nmbs_client.get_liveboard.side_effect = lambda station_id: liveboard
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(liveboard_id)
    assert state is not None
    assert state.state == "Track 3 - Blankenberge"
    assert caplog.text.count("Unable to fetch the liveboard of Brussel-Noord") == 1
    assert caplog.text.count("Recovered feed: the liveboard of Brussel-Noord") == 1
