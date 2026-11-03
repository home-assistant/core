"""Tests for the Modern Forms diagnostics platform."""

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import init_integration, init_integration_gen4


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


async def test_entry_diagnostics_gen4(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Gen4 fixture names are redacted from diagnostics."""
    entry = await init_integration_gen4(hass, aioclient_mock)

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    fixture_names = [
        fixture["name"] for fixture in result["device"]["status"]["light_fixtures"]
    ]
    assert fixture_names == ["**REDACTED**", "**REDACTED**"]
    assert result == snapshot(exclude=props("created_at", "modified_at", "entry_id"))
