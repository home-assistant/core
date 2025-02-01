"""Test Homee entity in general."""

from unittest.mock import MagicMock

from homeassistant.components.homee.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import build_mock_node, setup_integration
from .conftest import HOMEE_ID, HOMEE_NAME

from tests.common import MockConfigEntry


async def test_general_data(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test if data is set correctly."""
    mock_homee.nodes = [build_mock_node("cover_with_position_slats.json")]
    await setup_integration(hass, mock_config_entry)

    # Verify hub created correctly.
    hub = device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{HOMEE_ID}")}
    )
    assert hub.name == HOMEE_NAME
    assert hub.manufacturer == "homee"
    assert hub.model == "homee"
    assert hub.sw_version == "1.2.3"
    assert hub.connections == {("mac", dr.format_mac(HOMEE_ID))}

    # verify device created correctly.
    device = device_registry.async_get_device(identifiers={(DOMAIN, f"{HOMEE_ID}-3")})
    assert device.model == "shutter_position_switch"
    assert device.sw_version == "4.54"
    assert device.via_device_id == hub.id

    # Verify entities with correct data present.
    # For a HomeeEntity.
    temp_sensor = hass.states.get("sensor.test_cover_temperature")
    attributes = temp_sensor.attributes
    assert attributes["friendly_name"] == "Test Cover Temperature"
    assert (
        entity_registry.async_get(temp_sensor.entity_id).unique_id == f"{HOMEE_ID}-3-4"
    )

    # For a HomeeNodeEntity.
    cover = hass.states.get("cover.test_cover")
    attributes = cover.attributes
    assert attributes["friendly_name"] == "Test Cover"
    assert entity_registry.async_get(cover.entity_id).unique_id == f"{HOMEE_ID}-3-1"

    # For a NodeSensor.
    node_state = entity_registry.async_get("sensor.test_cover_none")
    assert node_state.disabled
    assert node_state.unique_id == f"{HOMEE_ID}-3-state"


async def test_connection_listener(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if loss of connection is sensed correctly."""
    mock_homee.nodes = [build_mock_node("cover_with_position_slats.json")]
    await setup_integration(hass, mock_config_entry)

    states = hass.states.get("cover.test_cover")
    assert states.state != STATE_UNAVAILABLE

    mock_homee.add_connection_listener.call_args_list[1][0][0](False)
    await hass.async_block_till_done()

    states = hass.states.get("cover.test_cover")
    assert states.state == STATE_UNAVAILABLE

    mock_homee.add_connection_listener.call_args_list[1][0][0](True)
    await hass.async_block_till_done()

    states = hass.states.get("cover.test_cover")
    assert states.state != STATE_UNAVAILABLE


async def test_homee_entity_listener(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test update listener of HomeeEntity."""
    mock_homee.nodes = [build_mock_node("cover_with_position_slats.json")]
    await setup_integration(hass, mock_config_entry)

    states = hass.states.get("sensor.test_cover_temperature")
    assert states.state == "20.3"
    assert states.attributes["friendly_name"] == "Test Cover Temperature"
    assert states.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert states.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
    assert states.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS

    temp_sensor = mock_homee.nodes[0].attributes[3]
    temp_sensor.current_value = -5.2
    temp_sensor.add_on_changed_listener.call_args_list[0][0][0](temp_sensor)
    await hass.async_block_till_done()

    states = hass.states.get("sensor.test_cover_temperature")
    assert states.state == "-5.2"


async def test_homee_node_entity_listener(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test update listener of HomeeNodeEntity."""
    mock_homee.nodes = [build_mock_node("cover_with_position_slats.json")]
    await setup_integration(hass, mock_config_entry)


async def test_unload_entry(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading of config entry."""
    mock_homee.nodes = [build_mock_node("cover_with_position_slats.json")]
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
