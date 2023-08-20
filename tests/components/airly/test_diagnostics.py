"""Test Airly diagnostics."""
import json

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    entry = await init_integration(hass, aioclient_mock)

    json.loads(load_fixture("diagnostics_data.json", "airly"))

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == snapshot
