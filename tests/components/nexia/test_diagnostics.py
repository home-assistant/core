"""Test august diagnostics."""
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .util import async_init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    entry = await async_init_integration(hass)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == snapshot
