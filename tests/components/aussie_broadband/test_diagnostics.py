"""Test the Aussie Broadband Diagnostics."""

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_select_async_setup_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics platform."""

    entry = await setup_platform(hass, [])
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == snapshot
