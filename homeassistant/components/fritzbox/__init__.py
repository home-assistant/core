"""Support for AVM Fritz!Box smarthome devices."""
import asyncio
import socket

from pyfritzhome import Fritzhome
import voluptuous as vol

from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv

from .const import CONF_CONNECTIONS, DEFAULT_HOST, DEFAULT_USERNAME, DOMAIN, PLATFORMS


def ensure_unique_hosts(value):
    """Validate that all configs have a unique host."""
    vol.Schema(vol.Unique("duplicate host entries found"))(
        [socket.gethostbyname(entry[CONF_HOST]) for entry in value]
    )
    return value


CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_DEVICES): vol.All(
                        cv.ensure_list,
                        [
                            vol.Schema(
                                {
                                    vol.Required(
                                        CONF_HOST, default=DEFAULT_HOST
                                    ): cv.string,
                                    vol.Required(CONF_PASSWORD): cv.string,
                                    vol.Required(
                                        CONF_USERNAME, default=DEFAULT_USERNAME
                                    ): cv.string,
                                }
                            )
                        ],
                        ensure_unique_hosts,
                    )
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the AVM Fritz!Box integration."""
    if DOMAIN in config:
        for entry_config in config[DOMAIN][CONF_DEVICES]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": "import"}, data=entry_config
                )
            )

    return True


async def async_setup_entry(hass, entry):
    """Set up the AVM Fritz!Box platforms."""
    fritz = Fritzhome(
        host=entry.data[CONF_HOST],
        user=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )
    await hass.async_add_executor_job(fritz.login)

    hass.data.setdefault(DOMAIN, {CONF_CONNECTIONS: {}, CONF_DEVICES: set()})
    hass.data[DOMAIN][CONF_CONNECTIONS][entry.entry_id] = fritz

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    def logout_fritzbox(event):
        """Close connections to this fritzbox."""
        fritz.logout()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, logout_fritzbox)

    return True


async def async_unload_entry(hass, entry):
    """Unloading the AVM Fritz!Box platforms."""
    fritz = hass.data[DOMAIN][CONF_CONNECTIONS][entry.entry_id]
    await hass.async_add_executor_job(fritz.logout)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN][CONF_CONNECTIONS].pop(entry.entry_id)

    return unload_ok
