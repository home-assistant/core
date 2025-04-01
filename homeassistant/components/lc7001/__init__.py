"""The Legrand Whole House Lighting integration."""

import logging

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .common import LcConfigEntry
from .engine.engine import ConnectionState, Engine

_PLATFORMS: list[Platform] = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: LcConfigEntry) -> bool:
    """Set up Legrand Whole House Lighting from a config entry."""

    engine = Engine(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        engine.connect()
        engine.start()
        await engine.waitForState(ConnectionState.Ready)
    except TimeoutError:
        return False

    entry.runtime_data = engine
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LcConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
