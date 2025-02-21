"""Test bang_olufsen config entry diagnostics."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from .const import TEST_BUTTON_EVENT_ENTITY_ID

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    hass_client: ClientSessionGenerator,
    integration: tuple[MockConfigEntry, AsyncMock],
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    config_entry, client = integration

    # Enable an Event entity
    entity_registry.async_update_entity(TEST_BUTTON_EVENT_ENTITY_ID, disabled_by=None)
    hass.config_entries.async_schedule_reload(config_entry.entry_id)

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == snapshot(
        exclude=props(
            "created_at",
            "entry_id",
            "id",
            "last_changed",
            "last_reported",
            "last_updated",
            "media_position_updated_at",
            "modified_at",
        )
    )
