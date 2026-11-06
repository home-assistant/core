"""Test the NMBS sensors."""

from unittest.mock import AsyncMock

from pyrail import PyRailError
from pyrail.models import ConnectionsApiResponse, LiveboardApiResponse
from pytest_homeassistant.common import MockConfigEntry, async_load_json_object_fixture

from homeassistant.components.nmbs.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

STATION_FROM_ID = "BE.NMBS.008812005"
STATION_TO_ID = "BE.NMBS.008814001"
CONNECTION_UNIQUE_ID = f"nmbs_connection_{STATION_FROM_ID}_{STATION_TO_ID}"
LIVEBOARD_UNIQUE_ID = f"nmbs_live_{STATION_TO_ID}_{STATION_FROM_ID}_{STATION_TO_ID}"


async def test_connection_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the connection sensor reports the duration of the upcoming train."""
    connections = ConnectionsApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "connections.json", DOMAIN)
    )
    assert connections.connections is not None
    mock_nmbs_client.get_connections.return_value = connections
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, CONNECTION_UNIQUE_ID
    )
    assert entity_id is not None

    await async_update_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state is not None
    connection = connections.connections[1]
    expected = round(
        (connection.arrival.time - connection.departure.time).total_seconds() / 60
    ) + round(connection.departure.delay / 60)
    assert state.state == str(expected)
    assert state.attributes["delay_minutes"] == round(connection.departure.delay / 60)
    assert state.attributes["vehicle_id"] == connection.departure.vehicle

    mock_nmbs_client.get_connections.assert_called_once_with(
        STATION_FROM_ID, STATION_TO_ID
    )


async def test_connection_sensor_api_error_keeps_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the connection sensor keeps its state when the API fails."""
    mock_nmbs_client.get_connections.return_value = ConnectionsApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "connections.json", DOMAIN)
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, CONNECTION_UNIQUE_ID
    )
    assert entity_id is not None

    await async_update_entity(hass, entity_id)

    previous_state = hass.states.get(entity_id)
    assert previous_state is not None

    mock_nmbs_client.get_connections.side_effect = PyRailError("API unavailable")
    await async_update_entity(hass, entity_id)

    assert hass.states.get(entity_id).state == previous_state.state


async def test_connection_sensor_not_modified_keeps_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the connection sensor keeps its state when the data is not modified."""
    mock_nmbs_client.get_connections.return_value = ConnectionsApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "connections.json", DOMAIN)
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, CONNECTION_UNIQUE_ID
    )
    assert entity_id is not None

    await async_update_entity(hass, entity_id)

    previous_state = hass.states.get(entity_id)
    assert previous_state is not None

    mock_nmbs_client.get_connections.return_value = None
    await async_update_entity(hass, entity_id)

    assert hass.states.get(entity_id).state == previous_state.state


async def test_liveboard_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the liveboard sensor reports the next departure."""
    liveboard = LiveboardApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "liveboard.json", DOMAIN)
    )
    assert liveboard.departures is not None
    mock_nmbs_client.get_liveboard.return_value = liveboard
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, LIVEBOARD_UNIQUE_ID
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).disabled_by is not None

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await async_update_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state is not None
    departure = liveboard.departures[0]
    assert state.state == f"Track {departure.platform} - {departure.station}"
    assert state.attributes["vehicle_id"] == departure.vehicle
    assert state.attributes["delay_minutes"] == round(departure.delay / 60)

    mock_nmbs_client.get_liveboard.assert_called_once_with(station_id=STATION_TO_ID)


async def test_liveboard_sensor_api_error_keeps_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the liveboard sensor keeps its state when the API fails."""
    mock_nmbs_client.get_liveboard.return_value = LiveboardApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "liveboard.json", DOMAIN)
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, LIVEBOARD_UNIQUE_ID
    )
    assert entity_id is not None

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await async_update_entity(hass, entity_id)

    previous_state = hass.states.get(entity_id)
    assert previous_state is not None

    mock_nmbs_client.get_liveboard.side_effect = PyRailError("API unavailable")
    await async_update_entity(hass, entity_id)

    assert hass.states.get(entity_id).state == previous_state.state


async def test_liveboard_sensor_not_modified_keeps_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the liveboard sensor keeps its state when the data is not modified."""
    mock_nmbs_client.get_liveboard.return_value = LiveboardApiResponse.from_dict(
        await async_load_json_object_fixture(hass, "liveboard.json", DOMAIN)
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, LIVEBOARD_UNIQUE_ID
    )
    assert entity_id is not None

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await async_update_entity(hass, entity_id)

    previous_state = hass.states.get(entity_id)
    assert previous_state is not None

    mock_nmbs_client.get_liveboard.return_value = None
    await async_update_entity(hass, entity_id)

    assert hass.states.get(entity_id).state == previous_state.state
