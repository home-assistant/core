"""Support for OPNsense Routers."""
from dataclasses import dataclass

from pyopnsense import diagnostics
import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

from .const import CONF_API_SECRET, CONF_TRACKER_INTERFACE, DOMAIN, OPNSENSE_DATA

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.url,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_API_SECRET): cv.string,
                vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
                vol.Optional(CONF_TRACKER_INTERFACE, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@dataclass
class OPNsenseData:
    """Shared OPNsense data."""

    hass_config: dict


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the OPNsense component."""
    if config.get(DOMAIN) is not None:
        OPNsenseData.hass_config = config
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the OPNsense from a config entry."""

    api_data = {
        CONF_API_KEY: entry.data[CONF_API_KEY],
        CONF_API_SECRET: entry.data[CONF_API_SECRET],
        "base_url": entry.data[CONF_URL],
        "verify_cert": entry.data[CONF_VERIFY_SSL],
    }
    tracker_interfaces = entry.data.get(CONF_TRACKER_INTERFACE)

    hass.data[OPNSENSE_DATA] = {
        "interface_client": diagnostics.InterfaceClient(**api_data),
        CONF_TRACKER_INTERFACE: tracker_interfaces,
    }

    if tracker_interfaces:
        await async_load_platform(
            hass, DEVICE_TRACKER, DOMAIN, tracker_interfaces, OPNsenseData.hass_config
        )
    return True
