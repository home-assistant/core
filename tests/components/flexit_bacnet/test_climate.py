"""Tests for the Flexit Nordic (BACnet) climate entity."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from tests.common import MockConfigEntry
from tests.components.flexit_bacnet import setup_with_selected_platforms

ENTITY_CLIMATE = "climate.device_name"


async def test_climate_entity(
    hass: HomeAssistant,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the initial parameters."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    assert hass.states.get(ENTITY_CLIMATE) == snapshot
    assert entity_registry.async_get(ENTITY_CLIMATE) == snapshot
