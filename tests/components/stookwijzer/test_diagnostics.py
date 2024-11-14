"""Test the Stookwijzer diagnostics."""

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_get_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the Stookwijzer diagnostics."""
    entry = await setup_integration(hass, aioclient_mock, True, True)
    coordinator = entry.runtime_data

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == {
        "advice": coordinator.client.advice,
        "air_quality_index": coordinator.client.lki,
        "windspeed_bft": coordinator.client.windspeed_bft,
        "windspeed_ms": coordinator.client.windspeed_ms,
        "forecast_advice": coordinator.client.forecast_advice,
        "last_updated": coordinator.client.last_updated.isoformat(),
    }
