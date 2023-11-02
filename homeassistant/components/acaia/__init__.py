"""Initialize the Acaia component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .acaiaclient import AcaiaClient
from .const import CONF_IS_NEW_STYLE_SCALE, DOMAIN
from .coordinator import AcaiaApiCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Acaia as config entry."""

    name = config_entry.data[CONF_NAME]
    mac = config_entry.data[CONF_MAC]
    is_new_style_scale = config_entry.data.get(CONF_IS_NEW_STYLE_SCALE, True)

    acaia_client = AcaiaClient(
        hass, mac=mac, name=name, is_new_style_scale=is_new_style_scale
    )

    hass.data.setdefault(DOMAIN, {})[
        config_entry.entry_id
    ] = coordinator = AcaiaApiCoordinator(hass, acaia_client)

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
