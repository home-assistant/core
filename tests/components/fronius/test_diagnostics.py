"""Tests for the diagnostics data provided by the KNX integration."""

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import mock_responses, setup_fronius_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    mock_responses(aioclient_mock)
    entry = await setup_fronius_integration(hass)

    assert (
        await get_diagnostics_for_config_entry(
            hass,
            hass_client,
            entry,
        )
        == snapshot
    )
