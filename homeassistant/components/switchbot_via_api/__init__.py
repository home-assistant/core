"""The Switchbot via API integration."""
from logging import getLogger

from switchbot_api import Device, Remote, SwitchBotAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .const import API, DOMAIN

_LOGGER = getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up Switchbot via API from a config entry."""
    token = config.data.get(CONF_API_TOKEN)
    secret = config.data.get(CONF_API_KEY)

    if not token or not secret:
        _LOGGER.debug("Missing token or secret key")
        return False

    api = SwitchBotAPI(token=token, secret=secret)
    devices = await api.list_devices()
    _LOGGER.debug("Devices: %s", devices)
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][API] = api
    hass.data[DOMAIN][Platform.SWITCH] = [
        device
        for device in devices
        if isinstance(device, Device)
        and device.device_type.startswith("Plug")
        or isinstance(device, Remote)
    ]
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config, "switch")
    )
    return True
