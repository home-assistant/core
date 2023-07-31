"""Test Airly diagnostics."""
import json

from homeassistant.components.diagnostics import REDACTED
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
) -> None:
    """Test config entry diagnostics."""
    entry = await init_integration(hass, aioclient_mock)

    coordinator_data = json.loads(load_fixture("diagnostics_data.json", "airly"))

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["config_entry"] == {
        "entry_id": entry.entry_id,
        "version": 1,
        "domain": "airly",
        "title": "Home",
        "data": {
            "latitude": REDACTED,
            "longitude": REDACTED,
            "name": "Home",
            "api_key": REDACTED,
        },
        "options": {},
        "pref_disable_new_entities": False,
        "pref_disable_polling": False,
        "source": "user",
        "unique_id": REDACTED,
        "disabled_by": None,
    }
    assert result["coordinator_data"] == coordinator_data
