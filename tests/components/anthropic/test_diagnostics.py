"""Test Anthropic diagnostics."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    # Remove non-deterministic values from diagnostics.
    assert diagnostics.pop("client").startswith("anthropic==")
    diagnostics.pop("entry_id")
    subentries = diagnostics.pop("subentries")
    diagnostics["subentries"] = [
        subentry for subentry_id, subentry in subentries.items()
    ]
    for entity_id, entity in diagnostics["entities"].copy().items():
        for key in (
            "config_entry_id",
            "config_subentry_id",
            "created_at",
            "device_id",
            "id",
            "modified_at",
            "unique_id",
        ):
            if key in entity:
                entity.pop(key)
        diagnostics["entities"][entity_id] = entity

    assert diagnostics == snapshot
