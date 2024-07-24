"""Test Jellyfin diagnostics."""

from syrupy import SnapshotAssertion
from syrupy.filters import paths

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import snapshot_get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    data = await snapshot_get_diagnostics_for_config_entry(
        hass,
        hass_client,
        init_integration,
        snapshot(exclude=paths("entry.data.client_device_id")),
    )
    assert data["entry"]["data"]["client_device_id"] == init_integration.entry_id
