"""Tests for the Zinvolt select."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion
from zinvolt.models import SmartMode

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_zinvolt_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.zinvolt._PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_option(
    hass: HomeAssistant,
    mock_zinvolt_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set option."""
    await setup_integration(hass, mock_config_entry)

    mock_zinvolt_client.get_battery_status.return_value.smart_mode = (
        SmartMode.PERFORMANCE
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.zinvolt_batterij_mode",
            ATTR_OPTION: "fast_discharge",
        },
        blocking=True,
    )

    mock_zinvolt_client.set_smart_mode.assert_called_once_with(
        "a125ef17-6bdf-45ad-b106-ce54e95e4634", SmartMode.PERFORMANCE
    )
    assert hass.states.get("select.zinvolt_batterij_mode").state == "fast_discharge"
