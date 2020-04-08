"""The Bosch Smart Home Controller integration."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util import slugify

from .const import CONF_SSL_CERTIFICATE, CONF_SSL_KEY, DOMAIN

ENTITY_ID_FORMAT = DOMAIN + ".{}"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_NAME, default="Home"): cv.string,
                vol.Required(CONF_IP_ADDRESS): cv.string,
                vol.Required(CONF_SSL_CERTIFICATE): cv.isfile,
                vol.Required(CONF_SSL_KEY): cv.isfile,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [
    "binary_sensor",
]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Bosch SHC component."""
    hass.data.setdefault(DOMAIN, {})
    conf = config.get(DOMAIN)

    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Bosch SHC from a config entry."""
    from boschshcpy import SHCSession

    data = entry.data

    _LOGGER.debug("Connecting to Bosch Smart Home Controller API")
    session = await hass.async_add_executor_job(
        SHCSession,
        data[CONF_IP_ADDRESS],
        data[CONF_SSL_CERTIFICATE],
        data[CONF_SSL_KEY],
    )

    shc_info = session.information
    if shc_info.version == "n/a":
        _LOGGER.error("Unable to connect to Bosch Smart Home Controller API")
        return False
    elif shc_info.updateState.name == "UPDATE_AVAILABLE":
        _LOGGER.warning("Please check for software updates in the Bosch Smart Home App")

    hass.data[DOMAIN][slugify(data[CONF_NAME])] = session

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, data[CONF_IP_ADDRESS])},
        manufacturer="Bosch",
        name=data[CONF_NAME],
        model="SmartHomeController",
        sw_version=shc_info.version,
    )

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    # async def stop_polling(event):
    #     """Stop polling service."""
    #     await hass.async_add_executor_job(session.stop_polling)

    # async def start_polling(event):
    #     """Start polling service."""
    #     await hass.async_add_executor_job(session.start_polling)
    #     hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_polling)

    # hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_polling)

    await hass.async_add_executor_job(session.start_polling)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    from boschshcpy import SHCSession

    session: SHCSession = hass.data[DOMAIN][slugify(entry.data[CONF_NAME])]
    await hass.async_add_executor_job(session.stop_polling)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(slugify(entry.data[CONF_NAME]))

    return unload_ok
