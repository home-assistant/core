"""The keenetic_ndms2 component."""

from homeassistant.components import binary_sensor, device_tracker
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CONSIDER_HOME,
    CONF_INCLUDE_ARP,
    CONF_INCLUDE_ASSOCIATED,
    CONF_INTERFACES,
    CONF_TRY_HOTSPOT,
    DEFAULT_CONSIDER_HOME,
    DEFAULT_INTERFACE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ROUTER,
    UNDO_UPDATE_LISTENER,
)
from .router import KeeneticRouter

PLATFORMS = [device_tracker.DOMAIN, binary_sensor.DOMAIN]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the component."""
    hass.data.setdefault(DOMAIN, {})
    async_add_defaults(hass, config_entry)

    router = KeeneticRouter(hass, config_entry)
    await router.async_setup()

    undo_listener = config_entry.add_update_listener(update_listener)

    hass.data[DOMAIN][config_entry.entry_id] = {
        ROUTER: router,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN][config_entry.entry_id][UNDO_UPDATE_LISTENER]()

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    router: KeeneticRouter = hass.data[DOMAIN][config_entry.entry_id][ROUTER]

    await router.async_teardown()

    hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(hass, config_entry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


def async_add_defaults(hass: HomeAssistant, config_entry: ConfigEntry):
    """Populate default options."""
    host: str = config_entry.data[CONF_HOST]
    imported_options: dict = hass.data[DOMAIN].get(f"imported_options_{host}", {})
    options = {
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_CONSIDER_HOME: DEFAULT_CONSIDER_HOME,
        CONF_INTERFACES: [DEFAULT_INTERFACE],
        CONF_TRY_HOTSPOT: True,
        CONF_INCLUDE_ARP: True,
        CONF_INCLUDE_ASSOCIATED: True,
        **imported_options,
        **config_entry.options,
    }

    if options.keys() - config_entry.options.keys():
        hass.config_entries.async_update_entry(config_entry, options=options)
