"""Test the Z-Wave JS helpers module."""
import voluptuous as vol

from homeassistant.components.zwave_js.helpers import (
    async_get_node_status_sensor_entity_id,
    async_get_nodes_from_area_id,
    get_value_state_schema,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr

from tests.common import MockConfigEntry


async def test_async_get_node_status_sensor_entity_id(hass: HomeAssistant) -> None:
    """Test async_get_node_status_sensor_entity_id for non zwave_js device."""
    dev_reg = dr.async_get(hass)
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "test")},
    )
    assert async_get_node_status_sensor_entity_id(hass, device.id) is None


async def test_async_get_nodes_from_area_id(hass: HomeAssistant) -> None:
    """Test async_get_nodes_from_area_id."""
    area_reg = ar.async_get(hass)
    area = area_reg.async_create("test")
    assert not async_get_nodes_from_area_id(hass, area.id)


async def test_get_value_state_schema_boolean_config_value(
    hass: HomeAssistant, client, aeon_smart_switch_6
) -> None:
    """Test get_value_state_schema for boolean config value."""
    schema_validator = get_value_state_schema(
        aeon_smart_switch_6.values["102-112-0-255"]
    )
    assert isinstance(schema_validator, vol.Coerce)
    assert schema_validator.type == bool
