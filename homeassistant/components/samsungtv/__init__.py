"""The Samsung TV integration."""
import socket

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player.const import DOMAIN as MP_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .bridge import SamsungTVBridge
from .const import CONF_ON_ACTION, DEFAULT_NAME, DOMAIN, LOGGER


def ensure_unique_hosts(value):
    """Validate that all configs have a unique host."""
    vol.Schema(vol.Unique("duplicate host entries found"))(
        [entry[CONF_HOST] for entry in value]
    )
    return value


PLATFORMS = [MP_DOMAIN]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                cv.deprecated(CONF_PORT),
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                        vol.Optional(CONF_PORT): cv.port,
                        vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
                    }
                ),
            ],
            ensure_unique_hosts,
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Samsung TV integration."""
    hass.data[DOMAIN] = {}
    if DOMAIN not in config:
        return True

    for entry_config in config[DOMAIN]:
        ip_address = await hass.async_add_executor_job(
            socket.gethostbyname, entry_config[CONF_HOST]
        )
        hass.data[DOMAIN][ip_address] = {
            CONF_ON_ACTION: entry_config.get(CONF_ON_ACTION)
        }
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=entry_config,
            )
        )
    return True


@callback
def _async_get_device_bridge(data):
    """Get device bridge."""
    return SamsungTVBridge.get_bridge(
        data[CONF_METHOD],
        data[CONF_HOST],
        data[CONF_PORT],
        data.get(CONF_TOKEN),
    )


async def async_setup_entry(hass, entry):
    """Set up the Samsung TV platform."""

    # Initialize bridge
    data = entry.data.copy()
    bridge = _async_get_device_bridge(data)
    if bridge.port is None and bridge.default_port is not None:
        # For backward compat, set default port for websocket tv
        data[CONF_PORT] = bridge.default_port
        hass.config_entries.async_update_entry(entry, data=data)
        bridge = _async_get_device_bridge(data)

    def stop_bridge(event):
        """Stop SamsungTV bridge connection."""
        bridge.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_bridge)
    )

    hass.data[DOMAIN][entry.entry_id] = bridge
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][entry.entry_id].stop()
    return unload_ok


async def async_migrate_entry(hass, config_entry):
    """Migrate old entry."""
    version = config_entry.version

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Unique ID format changed, so delete and re-import:
    if version == 1:
        dev_reg = await hass.helpers.device_registry.async_get_registry()
        dev_reg.async_clear_config_entry(config_entry)

        en_reg = await hass.helpers.entity_registry.async_get_registry()
        en_reg.async_clear_config_entry(config_entry)

        version = config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry)
    LOGGER.debug("Migration to version %s successful", version)

    return True
