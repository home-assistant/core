"""Test the Z-Wave JS helpers module."""
from homeassistant.components.zwave_js.helpers import (
    async_get_node_status_sensor_entity_id,
    async_get_nodes_from_area_id,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr


async def test_async_get_node_status_sensor_entity_id(hass: HomeAssistant) -> None:
    """Test async_get_node_status_sensor_entity_id for non zwave_js device."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id="123",
        identifiers={("test", "test")},
    )
    assert async_get_node_status_sensor_entity_id(hass, device.id) is None


async def test_async_get_nodes_from_area_id(hass: HomeAssistant) -> None:
    """Test async_get_nodes_from_area_id."""
    area_reg = ar.async_get(hass)
    area = area_reg.async_create("test")
    assert not async_get_nodes_from_area_id(hass, area.id)
