"""Test Jellyfin diagnostics."""

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


async def test_diagnostics(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    data = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert data["entry"]["data"]["client_device_id"] == init_integration.entry_id
    data["entry"]["data"]["client_device_id"] = "entry-id"

    assert data == snapshot
