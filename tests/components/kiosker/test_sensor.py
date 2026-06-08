"""Test the Kiosker sensors."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    mock_kiosker_api.blackout_get.return_value = SimpleNamespace(
        visible=True,
        dismissible=True,
        text="Hello world",
        icon="star.fill",
        background="#B10A10",
        foreground="#f0fA12",
        expire=60,
        buttonBackground="#c21c1c",
        buttonForeground="#36E20B",
        buttonText="Dismiss me",
        sound="1007",
    )

    with patch("homeassistant.components.kiosker._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        ):
            if entity_entry.disabled_by is not None:
                entity_registry.async_update_entity(
                    entity_entry.entity_id, disabled_by=None
                )
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
