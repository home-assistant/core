"""Tests for envisalink sensor."""


from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .common import (
    KEEP_ALIVE_PATCH,
    PARTITIONS,
    PERIODIC_PATCH,
    RECONNECT_PATCH,
    setup_platform,
)


async def test_sensor_entity_registry(hass: HomeAssistant) -> None:
    """Test the sensors are registered in entity registry."""
    with patch(KEEP_ALIVE_PATCH, return_value=None), patch(
        PERIODIC_PATCH, return_value=None
    ), patch(RECONNECT_PATCH, return_value=None):
        await setup_platform(hass)
        entity_registry = er.async_get(hass)
        for partition_id, partition_info in PARTITIONS.items():
            partition_name = partition_info["name"]
            entity_id = f"sensor.{slugify(partition_name)}_keypad"
            entity = entity_registry.async_get(entity_id)
            assert entity.unique_id == f"{partition_id}"
