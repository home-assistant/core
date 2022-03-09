"""Define tests for the Airzone init."""

from unittest.mock import patch

from homeassistant.components.airzone.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState

from .util import CONFIG, HVAC_MOCK

from tests.common import MockConfigEntry


async def test_unload_entry(hass):
    """Test unload."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="airzone_unique_id", data=CONFIG
    )
    config_entry.add_to_hass(hass)

    with patch(
        "aioairzone.localapi_device.AirzoneLocalApi.get_hvac",
        return_value=HVAC_MOCK,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED
