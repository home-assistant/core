"""Test init."""
from homeassistant.components.flo.const import DOMAIN as FLO_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import TEST_PASSWORD, TEST_USER_ID


async def test_setup_entry(
    hass: HomeAssistant, config_entry, aioclient_mock_fixture
) -> None:
    """Test migration of config entry from v1."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, FLO_DOMAIN, {CONF_USERNAME: TEST_USER_ID, CONF_PASSWORD: TEST_PASSWORD}
    )
    await hass.async_block_till_done()
    assert len(hass.data[FLO_DOMAIN][config_entry.entry_id]["devices"]) == 2

    assert await hass.config_entries.async_unload(config_entry.entry_id)
