"""The iskra integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pyiskra.adapters import Modbus, RestAPI
from pyiskra.devices import Device
from pyiskra.exceptions import DeviceConnectionError, DeviceNotSupported, NotAuthorised

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from .coordinator import IskraDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


type IskraConfigEntry = ConfigEntry[Device]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)
TIME_TILL_UNAVAILABLE = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: IskraConfigEntry) -> bool:
    """Set up iskra device from a config entry."""
    conf = entry.data
    adapter = None

    if conf[CONF_PROTOCOL] == "modbus_tcp":
        adapter = Modbus(
            ip_address=conf[CONF_HOST],
            protocol="tcp",
            port=conf[CONF_PORT],
            modbus_address=conf[CONF_ADDRESS],
        )
    elif conf[CONF_PROTOCOL] == "rest_api":
        authentication = None
        if conf.get(CONF_USERNAME) or conf.get(CONF_PASSWORD):
            authentication = {
                "username": conf[CONF_USERNAME],
                "password": conf[CONF_PASSWORD],
            }
        adapter = RestAPI(ip_address=conf[CONF_HOST], authentication=authentication)

    try:
        root_device = await Device.create_device(adapter)
    except DeviceConnectionError as e:
        _LOGGER.error("Cannot connect to the device: %s", e)
        return False
    except NotAuthorised as e:
        _LOGGER.error("Not authorised: %s", e)
        return False
    except DeviceNotSupported as e:
        _LOGGER.error("Device not supported: %s", e)
        return False

    await root_device.init()

    # if the device is a gateway, add all child devices, otherwise add the device itself.
    if root_device.is_gateway:
        coordinators = [
            IskraDataUpdateCoordinator(hass, child_device)
            for child_device in root_device.get_child_devices()
        ]
    else:
        coordinators = [IskraDataUpdateCoordinator(hass, root_device)]

    entry.runtime_data = {"base_evice": root_device, "coordinators": coordinators}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IskraConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
