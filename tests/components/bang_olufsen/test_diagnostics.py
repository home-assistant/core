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
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Enable an Event entity
    entity_registry.async_update_entity(TEST_BUTTON_EVENT_ENTITY_ID, disabled_by=None)
    hass.config_entries.async_schedule_reload(mock_config_entry.entry_id)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

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
