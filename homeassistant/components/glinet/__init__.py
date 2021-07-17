"""The GL-inet integration."""
from __future__ import annotations

from homeassistant.components.device_tracker.const import CONF_CONSIDER_HOME
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_GLINET, DOMAIN
from .router import GLinetRouter

PLATFORMS = ["device_tracker"]


async def async_setup(hass, config):
    """Set up the GLinet integration."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True

    # save the options from config yaml
    options = {}
    for name, value in conf.items():
        if name in ([CONF_CONSIDER_HOME]):
            options[name] = value
    hass.data[DOMAIN]["yaml_options"] = options

    # check if already configured
    domains_list = hass.config_entries.async_domains()
    if DOMAIN in domains_list:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GL-inet from a config entry."""
    yaml_options = hass.data.get(DOMAIN, {}).pop("yaml_options", {})
    if not entry.options and yaml_options:
        hass.config_entries.async_update_entry(entry, options=yaml_options)
    # TODO Store an API object for your platforms to access
    router = GLinetRouter(hass, entry)
    await router.setup()
    router.async_on_close(entry.add_update_listener(update_listener))
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id][DATA_GLINET] = router

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    hass.config_entries
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Update when config_entry options update."""
    router = hass.data[DOMAIN][entry.entry_id][DATA_GLINET]

    if router.update_options(entry.options):
        await hass.config_entries.async_reload(entry.entry_id)
