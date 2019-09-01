"""Support for devices connected to UniFi POE."""
import voluptuous as vol

from homeassistant.components.unifi.config_flow import (
    get_controller_id_from_config_entry,
)
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_MANUFACTURER,
    CONF_BLOCK_CLIENT,
    CONF_DETECTION_TIME,
    CONF_DONT_TRACK_CLIENTS,
    CONF_DONT_TRACK_DEVICES,
    CONF_DONT_TRACK_WIRED_CLIENTS,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    DOMAIN,
    UNIFI_CONFIG,
)
from .controller import UniFiController

CONF_CONTROLLERS = "controllers"

CONTROLLER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_SITE_ID): cv.string,
        vol.Optional(CONF_BLOCK_CLIENT, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_DONT_TRACK_CLIENTS): cv.boolean,
        vol.Optional(CONF_DONT_TRACK_DEVICES): cv.boolean,
        vol.Optional(CONF_DONT_TRACK_WIRED_CLIENTS): cv.boolean,
        vol.Optional(CONF_DETECTION_TIME): cv.positive_int,
        vol.Optional(CONF_SSID_FILTER): vol.All(cv.ensure_list, [cv.string]),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CONTROLLERS): vol.All(
                    cv.ensure_list, [CONTROLLER_SCHEMA]
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Component doesn't support configuration through configuration.yaml."""
    hass.data[UNIFI_CONFIG] = []

    if DOMAIN in config:
        hass.data[UNIFI_CONFIG] = config[DOMAIN][CONF_CONTROLLERS]

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the UniFi component."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    controller = UniFiController(hass, config_entry)

    controller_id = get_controller_id_from_config_entry(config_entry)

    hass.data[DOMAIN][controller_id] = controller

    if not await controller.async_setup():
        return False

    if controller.mac is None:
        return True

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, controller.mac)},
        manufacturer=ATTR_MANUFACTURER,
        model="UniFi Controller",
        name="UniFi Controller",
        # sw_version=config.raw['swversion'],
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    controller_id = get_controller_id_from_config_entry(config_entry)
    controller = hass.data[DOMAIN].pop(controller_id)
    return await controller.async_reset()
