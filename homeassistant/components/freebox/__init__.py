"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
import asyncio
import logging

from aiofreepybox.exceptions import HttpRequestError
import voluptuous as vol

from homeassistant.components.discovery import SERVICE_FREEBOX
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN, PLATFORMS
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_PORT): cv.port}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Freebox component from legacy config file."""
    conf = config.get(DOMAIN)

    async def discovery_dispatch(service, discovery_info):
        if conf is None:
            host = discovery_info.get("properties", {}).get("api_domain")
            port = discovery_info.get("properties", {}).get("https_port")
            _LOGGER.info("Discovered Freebox server: %s:%s", host, port)
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={CONF_HOST: host, CONF_PORT: port},
                )
            )

    discovery.async_listen(hass, SERVICE_FREEBOX, discovery_dispatch)

    if conf is None:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf,
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Freebox component."""
    fbx = FreeboxRouter(hass, entry)

    try:
        await fbx.setup()
    except HttpRequestError:
        _LOGGER.exception("Failed to connect to Freebox")
        return False

    hass.data[DOMAIN] = fbx

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    # Services
    async def async_freebox_reboot(call):
        """Handle reboot service call."""
        await fbx.reboot()

    hass.services.async_register(DOMAIN, "reboot", async_freebox_reboot)

    async def close_fbx(event):
        """Close Freebox connection on HA Stop."""
        await fbx.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_fbx)

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        fbx = hass.data[DOMAIN]
        await fbx.close()
        hass.data.pop(DOMAIN)

    return unload_ok
