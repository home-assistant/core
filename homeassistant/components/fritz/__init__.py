"""Support for AVM Fritz!Box functions."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .common import AvmWrapper, FritzData
from .const import (
    DATA_FRITZ,
    DEFAULT_SSL,
    DOMAIN,
    FRITZ_AUTH_EXCEPTIONS,
    FRITZ_EXCEPTIONS,
    PLATFORMS,
)
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up fritzboxtools from config entry."""
    _LOGGER.debug("Setting up FRITZ!Box Tools component")
    avm_wrapper = AvmWrapper(
        hass=hass,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        use_tls=entry.data.get(CONF_SSL, DEFAULT_SSL),
    )

    try:
        await avm_wrapper.async_setup(entry.options)
    except FRITZ_AUTH_EXCEPTIONS as ex:
        raise ConfigEntryAuthFailed from ex
    except FRITZ_EXCEPTIONS as ex:
        raise ConfigEntryNotReady from ex

    if (
        "X_AVM-DE_UPnP1" in avm_wrapper.connection.services
        and not (await avm_wrapper.async_get_upnp_configuration())["NewEnable"]
    ):
        raise ConfigEntryAuthFailed("Missing UPnP configuration")

    await avm_wrapper.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = avm_wrapper

    if DATA_FRITZ not in hass.data:
        hass.data[DATA_FRITZ] = FritzData()

    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Load the other platforms like switch
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload FRITZ!Box Tools config entry."""
    avm_wrapper: AvmWrapper = hass.data[DOMAIN][entry.entry_id]

    fritz_data = hass.data[DATA_FRITZ]
    fritz_data.tracked.pop(avm_wrapper.unique_id)

    if not bool(fritz_data.tracked):
        hass.data.pop(DATA_FRITZ)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    await async_unload_services(hass)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update when config_entry options update."""
    if entry.options:
        await hass.config_entries.async_reload(entry.entry_id)
