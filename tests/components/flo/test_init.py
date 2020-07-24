"""Test init."""
from homeassistant.components.flo.const import DOMAIN as FLO_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from .common import TEST_PASSWORD, TEST_USER_ID


async def test_setup_entry(hass, config_entry, aioclient_mock_fixture):
    """Test migration of config entry from v1."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, FLO_DOMAIN, {CONF_USERNAME: TEST_USER_ID, CONF_PASSWORD: TEST_PASSWORD}
    )
    await hass.async_block_till_done()
    assert len(hass.data[FLO_DOMAIN]["devices"]) == 1
