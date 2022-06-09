"""Common methods used across tests for Prosegur."""
from homeassistant.components.prosegur import DOMAIN as PROSEGUR_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

CONTRACT = "1234abcd"


async def setup_platform(hass):
    """Set up the Prosegur platform."""
    mock_entry = MockConfigEntry(
        domain=PROSEGUR_DOMAIN,
        data={
            "contract": "1234abcd",
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
            "country": "PT",
        },
    )
    mock_entry.add_to_hass(hass)

    assert await async_setup_component(hass, PROSEGUR_DOMAIN, {})
    await hass.async_block_till_done()

    return mock_entry
