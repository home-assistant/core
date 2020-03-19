"""The devolo_home_control integration."""
from devolo_home_control_api.homecontrol import HomeControl
from devolo_home_control_api.mydevolo import (
    Mydevolo,
    WrongCredentialsError,
    WrongUrlError,
)
import voluptuous as vol

from homeassistant.components import switch as ha_switch
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .config_flow import create_config_flow
from .const import DEFAULT_MPRM, DEFAULT_MYDEVOLO, DOMAIN, PLATFORMS

SUPPORTED_PLATFORMS = [ha_switch.DOMAIN]

SERVER_CONFIG_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Optional("mydevolo", default=DEFAULT_MYDEVOLO): cv.string,
            vol.Optional("mprm", default=DEFAULT_MPRM): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Required(CONF_USERNAME): cv.string,
        }
    )
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: SERVER_CONFIG_SCHEMA}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Get all devices and add them to hass."""
    mydevolo = Mydevolo()
    try:
        # We need this because of staging purposes, but don't want to show this on the UI
        mydevolo.url = config.get(DOMAIN).get("mydevolo")
        mydevolo.mprm = config.get(DOMAIN).get("mprm")
    except AttributeError:
        mydevolo.url = "https://www.mydevolo.com"
        mydevolo.mprm = "https://homecontrol.mydevolo.com"
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up the devolo account from a config entry."""
    conf = entry.data
    hass.data.setdefault(DOMAIN, {})

    try:
        mydevolo = Mydevolo.get_instance()
        mydevolo.user = conf.get(CONF_USERNAME)
        mydevolo.password = conf.get(CONF_PASSWORD)
    except (WrongCredentialsError, WrongUrlError):
        create_config_flow(hass=hass)
        return False

    if mydevolo.maintenance:
        return False

    gateway_id = mydevolo.gateway_ids[0]
    mprm_url = mydevolo.mprm

    try:
        hass.data[DOMAIN]["homecontrol"] = HomeControl(
            gateway_id=gateway_id, url=mprm_url
        )
    except ConnectionError:
        return False

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    # Listen when EVENT_HOMEASSISTANT_STOP is fired
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, hass.data[DOMAIN]["homecontrol"].websocket_disconnect
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(config_entry, "switch")

    if hass.data[DOMAIN]:
        hass.data[DOMAIN]["homecontrol"].websocket_disconnect()
        del hass.data[DOMAIN]["homecontrol"]
    return True
