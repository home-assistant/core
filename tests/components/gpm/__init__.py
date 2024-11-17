"""Tests for the GPM integration."""

from homeassistant.components.gpm._manager import RepositoryType, UpdateStrategy
from homeassistant.components.gpm.const import CONF_UPDATE_STRATEGY, DOMAIN
from homeassistant.const import CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TESTING_VERSIONS = "v0.8.8", "v0.9.9", "v1.0.0", "v2.0.0beta2"


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the GPM integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: RepositoryType.INTEGRATION,
            CONF_URL: "https://github.com/user/awesome-component",
            CONF_UPDATE_STRATEGY: UpdateStrategy.LATEST_TAG,
        },
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
