"""Common test fixtures and helpers for SMN Argentina integration."""

from homeassistant.components.smn_argentina.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant,
    latitude: float = -34.6217,
    longitude: float = -58.4258,
    name: str = "Ciudad de Buenos Aires",
) -> MockConfigEntry:
    """Set up the SMN Argentina integration in Home Assistant."""
    entry_data = {
        CONF_NAME: name,
        CONF_LATITUDE: latitude,
        CONF_LONGITUDE: longitude,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=entry_data,
        unique_id="4864",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
