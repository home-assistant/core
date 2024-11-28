from __future__ import annotations

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import CONF_INSTALLATION_ID, CONF_MODEL, CONF_SERIAL
from .victronvenus_base import VictronVenusConfigEntry
from .victronvenus_hub import VictronVenusHub


async def _async_setup_hub(
    hass: HomeAssistant, entry: VictronVenusConfigEntry, platforms: list[Platform]
) -> bool:
    """Set up victronvenus from a config entry."""

    config = entry.data
    hub = VictronVenusHub(
        hass,
        config.get(CONF_HOST),
        config.get(CONF_PORT, 1883),
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        config.get(CONF_SERIAL),
        config.get(CONF_SSL, False),
        config.get(CONF_INSTALLATION_ID),
        config.get(CONF_MODEL),
    )

    await hub.connect()

    await hub.setup_subscriptions()
    await hub.initiate_keep_alive()
    await hub.wait_for_first_refresh()

    entry.runtime_data = hub

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def _async_unload_hub(
    hass: HomeAssistant, entry: VictronVenusConfigEntry, platforms: list[Platform]
) -> bool:
    """Unload a config entry."""

    hub = entry.runtime_data
    if hub is not None:
        if isinstance(hub, VictronVenusHub):
            await hub.disconnect()
    return await hass.config_entries.async_unload_platforms(entry, platforms)
