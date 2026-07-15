"""Tests for the Mikrotik button platform."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_mikrotik_entry

from tests.common import snapshot_platform


async def test_button_entities_created(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Mikrotik button entities are created with expected values."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.BUTTON]):
        config_entry = await setup_mikrotik_entry(hass)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_button_press(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry
) -> None:
    """Test Mikrotik button entities press."""
    await setup_mikrotik_entry(
        hass,
        health_data=[
            {"name": "voltage", "value": 24.2},
        ],
        system_data=[
            {
                "cpu-load": 15,
                "total-memory": 0,
                "free-memory": 200,
                "total-hdd-space": 0,
                "free-hdd-space": 25,
                "uptime": None,
            }
        ],
    )

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.mikrotik_restart"},
        blocking=True,
    )

    mock_api.assert_called_with("/system/reboot")
