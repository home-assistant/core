"""Test the Stookwijzer coordinator."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_load_update_failed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Stookwijzer configuration entry loading and unloading."""
    entry = await setup_integration(hass, aioclient_mock, True, True)

    with patch(
        "stookwijzer.stookwijzerapi.Stookwijzer.async_get_stookwijzer",
        return_value=(None),
    ):
        await hass.config_entries.async_reload(entry.entry_id)
