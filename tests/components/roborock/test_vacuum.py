"""Tests for Roborock vacuums."""


from unittest.mock import patch

from homeassistant.components.roborock.const import (
    DOMAIN,
    SERVICE_VACUUM_SET_MOP_INTENSITY,
    SERVICE_VACUUM_SET_MOP_MODE,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

ENTITY_ID = "vacuum.roborock_s7_maxv"
DEVICE_ID = "abc123"


async def test_registry_entries(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests devices are registered in the entity registry."""
    await setup_platform(hass, Platform.VACUUM)
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == DEVICE_ID


async def test_roborock_vacuum_services(
    hass: HomeAssistant, bypass_api_fixture
) -> None:
    """Test vacuum services."""
    await setup_platform(hass, Platform.VACUUM)
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.send_command"
    ) as mock_local_api_command:
        # Test set mop intensity
        await hass.services.async_call(
            DOMAIN,
            SERVICE_VACUUM_SET_MOP_INTENSITY,
            {"entity_id": ENTITY_ID, "mop_intensity": "mild"},
            blocking=True,
        )
        assert mock_local_api_command.call_count == 1
        await hass.services.async_call(
            DOMAIN,
            SERVICE_VACUUM_SET_MOP_MODE,
            {"entity_id": ENTITY_ID, "mop_mode": "standard"},
            blocking=True,
        )
        assert mock_local_api_command.call_count == 2
