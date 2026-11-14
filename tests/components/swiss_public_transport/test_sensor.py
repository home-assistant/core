"""Tests for the swiss_public_transport sensor platform."""

from unittest.mock import AsyncMock, patch

from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.swiss_public_transport.const import (
    CONF_DESTINATION,
    CONF_START,
    CONF_TIME_FIXED,
    CONF_TIME_STATION,
    DEFAULT_UPDATE_TIME,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DESTINATION, START

from tests.test_config_entries import FrozenDateTimeFactory


@pytest.mark.freeze_time("2024-01-06T17:00:00+00:00")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_opendata_client: AsyncMock,
    swiss_public_transport_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.cookidoo.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, swiss_public_transport_config_entry)

    assert swiss_public_transport_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(
        hass, entity_registry, snapshot, swiss_public_transport_config_entry.entry_id
    )


@pytest.mark.parametrize(
    ("raise_error"),
    [OpendataTransportConnectionError, OpendataTransportError],
)
async def test_fetching_data(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_opendata_client: AsyncMock,
    swiss_public_transport_config_entry: MockConfigEntry,
    raise_error: Exception,
) -> None:
    """Test fetching data."""
    freezer.move_to("2024-01-06T17:00:00+00:00")
    await setup_integration(hass, swiss_public_transport_config_entry)

    assert swiss_public_transport_config_entry.state is ConfigEntryState.LOADED

    mock_opendata_client.async_get_data.assert_called()

    assert mock_opendata_client.async_get_data.call_count == 2

    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 8

    assert (
        hass.states.get("sensor.zurich_bern_departure").state
        == "2024-01-06T17:03:00+00:00"
    )
    assert (
        hass.states.get("sensor.zurich_bern_departure_1").state
        == "2024-01-06T17:04:00+00:00"
    )
    assert (
        hass.states.get("sensor.zurich_bern_departure_2").state
        == "2024-01-06T17:05:00+00:00"
    )
    assert (
        round(float(hass.states.get("sensor.zurich_bern_trip_duration").state), 3)
        == 0.003
    )
    assert hass.states.get("sensor.zurich_bern_platform").state == "0"
    assert hass.states.get("sensor.zurich_bern_transfers").state == "0"
    assert hass.states.get("sensor.zurich_bern_delay").state == "0"
    assert hass.states.get("sensor.zurich_bern_line").state == "T10"

    # Set new data and verify it
    mock_opendata_client.connections = (
        await async_load_json_array_fixture(hass, "connections.json", DOMAIN)
    )[3:6]
    freezer.tick(DEFAULT_UPDATE_TIME)
    async_fire_time_changed(hass)
    assert mock_opendata_client.async_get_data.call_count == 3
    assert (
        hass.states.get("sensor.zurich_bern_departure").state
        == "2024-01-06T17:06:00+00:00"
    )

    # Simulate fetch exception
    mock_opendata_client.async_get_data.side_effect = raise_error
    freezer.tick(DEFAULT_UPDATE_TIME)
    async_fire_time_changed(hass)
    assert mock_opendata_client.async_get_data.call_count == 4
    assert hass.states.get("sensor.zurich_bern_departure").state == "unavailable"

    # Recover and fetch new data again
    mock_opendata_client.async_get_data.side_effect = None
    mock_opendata_client.connections = (
        await async_load_json_array_fixture(hass, "connections.json", DOMAIN)
    )[6:9]
    freezer.tick(DEFAULT_UPDATE_TIME)
    async_fire_time_changed(hass)
    assert mock_opendata_client.async_get_data.call_count == 5
    assert (
        hass.states.get("sensor.zurich_bern_departure").state
        == "2024-01-06T17:09:00+00:00"
    )


@pytest.mark.parametrize(
    ("raise_error", "state"),
    [
        (OpendataTransportConnectionError, ConfigEntryState.SETUP_RETRY),
        (OpendataTransportError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_fetching_data_setup_exception(
    hass: HomeAssistant,
    mock_opendata_client: AsyncMock,
    swiss_public_transport_config_entry: MockConfigEntry,
    raise_error: Exception,
    state: ConfigEntryState,
) -> None:
    """Test fetching data with setup exception."""

    mock_opendata_client.async_get_data.side_effect = raise_error
    await setup_integration(hass, swiss_public_transport_config_entry)

    assert swiss_public_transport_config_entry.state is state


@pytest.mark.parametrize(
    ("config_data", "departure", "departure_2", "platform"),
    [
        pytest.param({}, "2024-01-06T17:04:00+00:00", "unknown", "1", id="now"),
        pytest.param(
            {CONF_TIME_FIXED: "18:03:00"},
            "2024-01-06T17:03:00+00:00",
            "2024-01-06T17:05:00+00:00",
            "0",
            id="fixed_time",
        ),
        pytest.param(
            {CONF_TIME_STATION: "arrival"},
            "2024-01-06T17:03:00+00:00",
            "2024-01-06T17:05:00+00:00",
            "0",
            id="arrival",
        ),
    ],
)
async def test_departed_connection(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_opendata_client: AsyncMock,
    config_data: dict[str, str],
    departure: str,
    departure_2: str,
    platform: str,
) -> None:
    """Test a departed connection is only dropped when tracking next departures."""
    freezer.move_to("2024-01-06T17:02:45+00:00")
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_START: START, CONF_DESTINATION: DESTINATION, **config_data},
        title=f"{START} {DESTINATION}",
    )
    await setup_integration(hass, config_entry)

    assert (
        hass.states.get("sensor.zurich_bern_departure").state
        == "2024-01-06T17:03:00+00:00"
    )
    assert (
        hass.states.get("sensor.zurich_bern_departure_2").state
        == "2024-01-06T17:05:00+00:00"
    )
    assert hass.states.get("sensor.zurich_bern_platform").state == "0"
    call_count = mock_opendata_client.async_get_data.call_count

    # Pass the grace period after the first departure, before the next update
    freezer.tick(46)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_opendata_client.async_get_data.call_count == call_count
    assert hass.states.get("sensor.zurich_bern_departure").state == departure
    assert hass.states.get("sensor.zurich_bern_departure_2").state == departure_2
    assert hass.states.get("sensor.zurich_bern_platform").state == platform


@pytest.mark.freeze_time("2024-01-06T17:03:45+00:00")
async def test_departed_connection_dropped_on_update(
    hass: HomeAssistant,
    mock_opendata_client: AsyncMock,
    swiss_public_transport_config_entry: MockConfigEntry,
) -> None:
    """Test a connection which already departed is dropped from an update."""
    await setup_integration(hass, swiss_public_transport_config_entry)

    assert (
        hass.states.get("sensor.zurich_bern_departure").state
        == "2024-01-06T17:04:00+00:00"
    )
