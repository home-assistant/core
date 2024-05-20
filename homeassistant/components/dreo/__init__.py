"""Dreo for Integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from .const import DOMAIN, PLATFORMS_CONFIG, MANAGER, PLATFORMS, FAN, FAN_DEVICE
from hscloud.hscloud import HsCloud

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up Dreo from as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    manager = HsCloud(username, password)
    login = await hass.async_add_executor_job(manager.login)
    if not login:
        _LOGGER.error("Unable to login to the Dreo server")
        return False

    platforms = []
    fan_devices = []
    devices = await hass.async_add_executor_job(manager.get_devices)
    for device in devices:
        _platforms = PLATFORMS_CONFIG.get(device.get("model"))
        for platform in _platforms:
            if platform == FAN:
                fan_devices.append(device)

        platforms.extend(_platforms)

    platforms = list(set(platforms))

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][config_entry.entry_id] = {
        MANAGER: manager,
        PLATFORMS: platforms,
        FAN_DEVICE: fan_devices
    }

    await hass.config_entries.async_forward_entry_setups(config_entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    platforms = hass.data[DOMAIN][config_entry.entry_id].get(PLATFORMS)
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, platforms
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
