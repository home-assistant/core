"""Test the Aussie Broadband Diagnostics."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .common import setup_platform

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_select_async_setup_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics platform."""

    entry = await setup_platform(hass, [])
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == snapshot
