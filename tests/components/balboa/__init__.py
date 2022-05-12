"""Test the Balboa Spa Client integration."""
from homeassistant.components.balboa.const import DOMAIN as BALBOA_DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

BALBOA_DEFAULT_PORT = 4257
TEST_HOST = "balboatest.localdomain"


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Mock integration setup."""
    config_entry = MockConfigEntry(
        domain=BALBOA_DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
        },
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
