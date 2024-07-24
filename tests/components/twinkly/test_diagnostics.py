"""Tests for the diagnostics of the twinkly component."""

from collections.abc import Awaitable, Callable

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import ClientMock

from tests.components.diagnostics import snapshot_get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

type ComponentSetup = Callable[[], Awaitable[ClientMock]]

DOMAIN = "twinkly"


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: ComponentSetup,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    await snapshot_get_diagnostics_for_config_entry(hass, hass_client, entry, snapshot)
