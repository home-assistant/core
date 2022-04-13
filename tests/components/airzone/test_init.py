"""Define tests for the Airzone init."""

from unittest.mock import patch

from homeassistant.components.airzone.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant

from .util import CONFIG, CONFIG_NO_ID, HVAC_MOCK

from tests.common import MockConfigEntry


async def test_migration_system_id(hass: HomeAssistant):
    """Test System ID config migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_NO_ID,
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.airzone.async_setup_entry", return_value=True):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.version == 2
    assert config_entry.data[CONF_ID] == 0


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="airzone_unique_id", data=CONFIG, version=2
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
        return_value=HVAC_MOCK,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED
