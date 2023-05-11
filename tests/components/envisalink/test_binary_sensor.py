"""Tests for envisalink binary_sensor."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .common import (
    KEEP_ALIVE_PATCH,
    PERIODIC_PATCH,
    RECONNECT_PATCH,
    ZONES,
    setup_platform,
)


async def test_binary_sensor_entity_registry(hass: HomeAssistant) -> None:
    """Test the binary sensors are registered in entity registry."""
    with patch(KEEP_ALIVE_PATCH, return_value=None), patch(
        PERIODIC_PATCH, return_value=None
    ), patch(RECONNECT_PATCH, return_value=None):
        await setup_platform(hass)
        entity_registry = er.async_get(hass)
        for zone_id, zone_info in ZONES.items():
            zone_name = zone_info["name"]
            zone_type = zone_info["type"]
            entity_id = f"binary_sensor.{slugify(zone_name)}"
            entity = entity_registry.async_get(entity_id)
            assert entity.unique_id == f"{zone_id}"
            assert entity.original_device_class == zone_type
