"""Test Homee initialization."""

from unittest.mock import MagicMock

from pyHomee import HomeeAuthFailedException, HomeeConnectionFailedException
import pytest

from homeassistant.components.homee.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import build_mock_node, setup_integration
from .conftest import HOMEE_ID, HOMEE_NAME

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "side_eff",
    [
        HomeeConnectionFailedException("connection timed out"),
        HomeeAuthFailedException("wrong username or password"),
    ],
)
async def test_connection_errors(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_eff: Exception,
) -> None:
    """Test if connection errors on startup are handled correctly."""
    mock_homee.get_access_token.side_effect = side_eff
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_connection_listener(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test if loss of connection is sensed correctly."""
    mock_homee.nodes = [build_mock_node("homee.json")]
    await setup_integration(hass, mock_config_entry)

    mock_homee.add_connection_listener.call_args_list[0][0][0](False)
    await hass.async_block_till_done()
    assert "Disconnected from Homee" in caplog.text
    mock_homee.add_connection_listener.call_args_list[0][0][0](True)
    await hass.async_block_till_done()
    assert "Reconnected to Homee" in caplog.text


async def test_general_data(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test if data is set correctly."""
    mock_homee.nodes = [
        build_mock_node("cover_with_position_slats.json"),
        build_mock_node("homee.json"),
    ]
    mock_homee.get_node_by_id = (
        lambda node_id: mock_homee.nodes[0] if node_id == 3 else mock_homee.nodes[1]
    )
    await setup_integration(hass, mock_config_entry)

    # Verify hub created correctly.
    hub = device_registry.async_get_device(identifiers={(DOMAIN, f"{HOMEE_ID}")})
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
    node_state = entity_registry.async_get("sensor.testhomee_node_state")
    assert node_state.disabled
    assert node_state.unique_id == f"{HOMEE_ID}--1-state"


async def test_software_version(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test sw_version for device with only AttributeType.SOFTWARE_VERSION."""
    mock_homee.nodes = [build_mock_node("cover_without_position.json")]
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, f"{HOMEE_ID}-3")})
    assert device.sw_version == "1.45"


async def test_invalid_profile(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test unknown value passed to get_name_for_enum."""
    mock_homee.nodes = [build_mock_node("cover_without_position.json")]
    # This is a profile, that does not exist in the enum.
    mock_homee.nodes[0].profile = 77
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, f"{HOMEE_ID}-3")})
    assert device.model is None


async def test_unload_entry(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading of config entry."""
    mock_homee.nodes = [build_mock_node("cover_with_position_slats.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
