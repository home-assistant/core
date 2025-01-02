"""VeSync integration."""

import logging

from pyvesync import VeSync

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .common import async_process_devices
from .const import DOMAIN, VS_FANS, VS_LIGHTS, VS_MANAGER, VS_SENSORS, VS_SWITCHES

PLATFORMS = [Platform.FAN, Platform.LIGHT, Platform.SENSOR, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Vesync as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    time_zone = str(hass.config.time_zone)

    manager = VeSync(username, password, time_zone)

    login = await hass.async_add_executor_job(manager.login)

    if not login:
        _LOGGER.error("Unable to login to the VeSync server")
        return False

    device_dict = await async_process_devices(hass, manager)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_MANAGER] = manager

    switches = hass.data[DOMAIN][VS_SWITCHES] = []
    fans = hass.data[DOMAIN][VS_FANS] = []
    lights = hass.data[DOMAIN][VS_LIGHTS] = []
    sensors = hass.data[DOMAIN][VS_SENSORS] = []
    platforms = []

    if device_dict[VS_SWITCHES]:
        switches.extend(device_dict[VS_SWITCHES])
        platforms.append(Platform.SWITCH)

    if device_dict[VS_FANS]:
        fans.extend(device_dict[VS_FANS])
        platforms.append(Platform.FAN)

    if device_dict[VS_LIGHTS]:
        lights.extend(device_dict[VS_LIGHTS])
        platforms.append(Platform.LIGHT)

    if device_dict[VS_SENSORS]:
        sensors.extend(device_dict[VS_SENSORS])
        platforms.append(Platform.SENSOR)

    await hass.config_entries.async_forward_entry_setups(config_entry, platforms)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    in_use_platforms = []
    if hass.data[DOMAIN][VS_SWITCHES]:
        in_use_platforms.append(Platform.SWITCH)
    if hass.data[DOMAIN][VS_FANS]:
        in_use_platforms.append(Platform.FAN)
    if hass.data[DOMAIN][VS_LIGHTS]:
        in_use_platforms.append(Platform.LIGHT)
    if hass.data[DOMAIN][VS_SENSORS]:
        in_use_platforms.append(Platform.SENSOR)
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, in_use_platforms
    )
    if unload_ok:
        hass.data.pop(DOMAIN)

    return unload_ok
