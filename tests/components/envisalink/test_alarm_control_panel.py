"""Tests for envisalink alarm control panel."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .common import PARTITIONS, setup_platform


@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_alarm_control_panel_entity_registry(hass: HomeAssistant) -> None:
    """Test the sensors are registered in entity registry."""
    await setup_platform(hass)
    entity_registry = er.async_get(hass)
    for partition_id, partition_info in PARTITIONS.items():
        partition_name = partition_info["name"]
        entity_id = f"alarm_control_panel.{slugify(partition_name)}"
        entity = entity_registry.async_get(entity_id)
        assert entity.unique_id == f"{partition_id}"
