"""Tests for the Modern Forms diagnostics platform."""

from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation and values of the Modern Forms fans."""
    entry = await init_integration(hass, aioclient_mock)

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == snapshot(exclude=props("created_at", "modified_at", "entry_id"))
