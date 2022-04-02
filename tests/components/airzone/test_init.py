"""Define tests for the Airzone init."""

from unittest.mock import MagicMock, patch

from aiohttp.client_exceptions import ClientResponseError

from homeassistant.components.airzone.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .util import CONFIG, HVAC_MOCK, HVAC_SYSTEMS_MOCK

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="airzone_unique_id", data=CONFIG
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
        return_value=HVAC_MOCK,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac_systems",
        return_value=HVAC_SYSTEMS_MOCK,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_webserver",
        side_effect=ClientResponseError(MagicMock(), MagicMock()),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED
