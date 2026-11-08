"""Test OVHcloud AI Endpoints diagnostics."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics.pop("client").startswith("openai==")
    diagnostics.pop("entry_id")
    subentries = diagnostics.pop("subentries")
    diagnostics["subentries"] = list(subentries.values())
    for entity in diagnostics["entities"].values():
        for key in (
            "config_entry_id",
            "config_subentry_id",
            "created_at",
            "device_id",
            "id",
            "modified_at",
            "unique_id",
        ):
            entity.pop(key, None)

    assert diagnostics == snapshot
