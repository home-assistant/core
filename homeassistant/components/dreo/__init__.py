"""Dreo for Integration."""
import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from .const import DOMAIN, PLATFORMS
from hscloud.const import DEVICE_TYPE, FAN_DEVICE
from hscloud.hscloud import HsCloud
from hscloud.hscloudexception import HsCloudException, HsCloudBusinessException

_LOGGER = logging.getLogger(__name__)

type MyConfigEntry = ConfigEntry[MyData]


@dataclass
class MyData:
    client: HsCloud
    fans: []


async def async_setup_entry(hass: HomeAssistant, config_entry: MyConfigEntry):
    """Set up Dreo from as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    manager = HsCloud(username, password)
    try:
        await hass.async_add_executor_job(manager.login)

    except HsCloudException as exc:
        _LOGGER.exception("unable to connect")
        return False

    except HsCloudBusinessException as exc:
        _LOGGER.exception("invalid username or password")
        return False

    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception")
        return False

    fans = []

    devices = await hass.async_add_executor_job(manager.get_devices)
    for device in devices:
        _device_type = DEVICE_TYPE.get(device.get("model"))
        if _device_type == FAN_DEVICE.get("type"):
            fans.append(device)

    config_entry.runtime_data = MyData(manager, fans)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    return unload_ok