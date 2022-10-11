"""Support for Atome devices connected to a Linky Energy Meter."""
import asyncio

from .const import DATA_COORDINATOR, DOMAIN

PLATFORMS = ["sensor"]

DATA_LISTENER = "listener"


async def async_setup(hass, config):
    """Set up the KeyAtome component."""
    # hass.data[DOMAIN] = {DATA_COORDINATOR: {}, DATA_LISTENER: {}}
    return True


async def async_setup_entry(hass, config_entry):
    """Set up KeyAtome as config entry."""
    hass.data.setdefault(DOMAIN, {DATA_COORDINATOR: {}, DATA_LISTENER: {}})

    # just to initialize (if data has to be forward to plateform)
    coordinator = None

    # To manage options
    hass.data[DOMAIN][DATA_LISTENER][
        config_entry.entry_id
    ] = config_entry.add_update_listener(async_reload_entry)

    # Useless
    hass.data[DOMAIN][DATA_COORDINATOR][config_entry.entry_id] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a KeyAtome config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:

        # remove config flow coordinator
        hass.data[DOMAIN][DATA_COORDINATOR].pop(config_entry.entry_id)
        remove_listener = hass.data[DOMAIN][DATA_LISTENER].pop(config_entry.entry_id)
        remove_listener()

    return unload_ok


async def async_reload_entry(hass, config_entry):
    """Handle an options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
