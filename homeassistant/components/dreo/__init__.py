"""Dreo for Integration."""
import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady

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

    except HsCloudException as ex:
        _LOGGER.exception("unable to connect")
        raise ConfigEntryNotReady(f"unable to connect") from ex

    except HsCloudBusinessException as ex:
        _LOGGER.exception("invalid username or password")
        raise ConfigEntryNotReady(f"invalid username or password") from ex

    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception")
        raise ConfigEntryNotReady(f"Unexpected exception") from ex

    devices = await hass.async_add_executor_job(manager.get_devices)

    fans = [
        device
        for device in devices
        if DEVICE_TYPE.get(device.get("model")) == FAN_DEVICE.get("type")
    ]

    config_entry.runtime_data = MyData(manager, fans)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    return unload_ok