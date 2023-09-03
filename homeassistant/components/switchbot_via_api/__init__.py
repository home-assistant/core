"""The Switchbot via API integration."""
from logging import getLogger

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .common import Device, Remote, SwitchBotAPI
from .const import API, DOMAIN, SECRET_KEY, TOKEN

_LOGGER = getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up Switchbot via API from a config entry."""
    token = config.data.get(TOKEN)
    secret = config.data.get(SECRET_KEY)

    if not token or not secret:
        _LOGGER.warning("Missing token or secret key")
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
    hass.data[DOMAIN][Platform.CLIMATE] = [
        device
        for device in devices
        if isinstance(device, Remote) and device.device_type.endswith("Air Conditioner")
    ]
    hass.data[DOMAIN][Platform.MEDIA_PLAYER] = [
        device
        for device in devices
        if isinstance(device, Remote)
        and any(
            device.device_type.endswith(type)
            for type in ("TV", "IPTV/Streamer", "Set Top Box", "DVD", "Speaker")
        )
    ]
    hass.data[DOMAIN][Platform.FAN] = [
        device
        for device in devices
        if isinstance(device, Remote) and device.device_type.endswith("Fan")
    ]
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config, "switch")
    )
    return True
