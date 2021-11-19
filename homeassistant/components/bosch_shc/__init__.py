"""The Bosch Smart Home Controller integration."""
import logging

from boschshcpy import SHCSession
from boschshcpy.exceptions import SHCAuthenticationError, SHCConnectionError

from homeassistant.components.zeroconf import async_get_instance
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DATA_POLLING_HANDLER,
    DATA_SESSION,
    DOMAIN,
)

PLATFORMS = ["binary_sensor", "cover", "sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bosch SHC from a config entry."""
    data = entry.data

    zeroconf = await async_get_instance(hass)
    try:
        session = await hass.async_add_executor_job(
            SHCSession,
            data[CONF_HOST],
            data[CONF_SSL_CERTIFICATE],
            data[CONF_SSL_KEY],
            False,
            zeroconf,
        )
    except SHCAuthenticationError as err:
        raise ConfigEntryAuthFailed from err
    except SHCConnectionError as err:
        raise ConfigEntryNotReady from err

    shc_info = session.information
    if shc_info.updateState.name == "UPDATE_AVAILABLE":
        _LOGGER.warning("Please check for software updates in the Bosch Smart Home App")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_SESSION: session,
    }

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(shc_info.unique_id))},
        identifiers={(DOMAIN, shc_info.unique_id)},
        manufacturer="Bosch",
        name=entry.title,
        model="SmartHomeController",
        sw_version=shc_info.version,
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def stop_polling(event):
        """Stop polling service."""
        await hass.async_add_executor_job(session.stop_polling)

    await hass.async_add_executor_job(session.start_polling)
    hass.data[DOMAIN][entry.entry_id][
        DATA_POLLING_HANDLER
    ] = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_polling)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    session: SHCSession = hass.data[DOMAIN][entry.entry_id][DATA_SESSION]

    hass.data[DOMAIN][entry.entry_id][DATA_POLLING_HANDLER]()
    hass.data[DOMAIN][entry.entry_id].pop(DATA_POLLING_HANDLER)
    await hass.async_add_executor_job(session.stop_polling)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
