"""Test the Advantage Air Diagnostics."""
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import add_mock_config, patch_get

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_select_async_setup_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test select platform."""

    with patch_get():
        entry = await add_mock_config(hass)
        diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
        assert diag == snapshot
