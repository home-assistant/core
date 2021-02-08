"""The Logitech Harmony Hub integration."""
import asyncio

from homeassistant.components.remote import ATTR_ACTIVITY, ATTR_DELAY_SECS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, HARMONY_OPTIONS_UPDATE, PLATFORMS
from .data import HarmonyData


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Logitech Harmony Hub component."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Logitech Harmony Hub from a config entry."""
    # As there currently is no way to import options from yaml
    # when setting up a config entry, we fallback to adding
    # the options to the config entry and pull them out here if
    # they are missing from the options
    _async_import_options_from_data_if_missing(hass, entry)

    address = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    data = HarmonyData(hass, address, name, entry.unique_id)
    try:
        connected_ok = await data.connect()
    except (asyncio.TimeoutError, ValueError, AttributeError) as err:
        raise ConfigEntryNotReady from err

    if not connected_ok:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = data

    entry.add_update_listener(_update_listener)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


@callback
def _async_import_options_from_data_if_missing(hass: HomeAssistant, entry: ConfigEntry):
    options = dict(entry.options)
    modified = 0
    for importable_option in [ATTR_ACTIVITY, ATTR_DELAY_SECS]:
        if importable_option not in entry.options and importable_option in entry.data:
            options[importable_option] = entry.data[importable_option]
            modified = 1

    if modified:
        hass.config_entries.async_update_entry(entry, options=options)


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    async_dispatcher_send(
        hass, f"{HARMONY_OPTIONS_UPDATE}-{entry.unique_id}", entry.options
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    # Shutdown a harmony remote for removal
    data = hass.data[DOMAIN][entry.entry_id]
    await data.shutdown()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
