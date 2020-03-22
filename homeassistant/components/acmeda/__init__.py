"""The Rollease Acmeda Automate integration."""
import ipaddress
import logging

import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .hub import PulseHub

_LOGGER = logging.getLogger(__name__)

CONF_HUBS = "hubs"

DATA_CONFIGS = "pulse_configs"

HUB_CONFIG_SCHEMA = vol.Schema(
    {
        # Validate as IP address and then convert back to a string.
        vol.Required(CONF_HOST): vol.All(ipaddress.ip_address, cv.string),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HUBS): vol.All(
                    cv.ensure_list, [vol.All(HUB_CONFIG_SCHEMA)],
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: core.HomeAssistant, config: dict):
    """Set up the Rollease Acmeda Automate component."""
    conf = config.get(DOMAIN)
    if conf is None:
        conf = {}

    hass.data[DOMAIN] = {}
    hass.data[DATA_CONFIGS] = {}

    # User has configured hubs
    if CONF_HUBS not in conf:
        return True

    hubs = conf[CONF_HUBS]

    configured_hosts = set(
        entry.data.get("host") for entry in hass.config_entries.async_entries(DOMAIN)
    )

    for hub_conf in hubs:
        host = hub_conf[CONF_HOST]

        # Store config in hass.data so the config entry can find it
        hass.data[DATA_CONFIGS][host] = hub_conf

        if host in configured_hosts:
            continue

        # No existing config entry found, trigger link config flow. Because we're
        # inside the setup of this component we'll have to use hass.async_add_job
        # to avoid a deadlock: creating a config entry will set up the component
        # but the setup would block till the entry is created!
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={"host": hub_conf[CONF_HOST]},
            )
        )

    return True


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Set up Rollease Acmeda Automate hub from a config entry."""
    host = entry.data["host"]
    config = hass.data[DATA_CONFIGS].get(host)

    if config is None:
        pass
    else:
        pass

    hub = PulseHub(hass, entry)

    if not await hub.async_setup():
        return False

    hass.data[DOMAIN][host] = hub

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Unload a config entry."""
    hub = hass.data[DOMAIN].pop(entry.data["host"])
    return await hub.async_reset()
