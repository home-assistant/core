"""The iskra integration."""

from __future__ import annotations

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
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MANUFACTURER
from .coordinator import IskraDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


type IskraConfigEntry = ConfigEntry[list[IskraDataUpdateCoordinator]]


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
        if (username := conf.get(CONF_USERNAME)) is not None and (
            password := conf.get(CONF_PASSWORD)
        ) is not None:
            authentication = {
                "username": username,
                "password": password,
            }
        adapter = RestAPI(ip_address=conf[CONF_HOST], authentication=authentication)

    # Try connecting to the device and create pyiskra device object
    try:
        base_device = await Device.create_device(adapter)
    except DeviceConnectionError as e:
        raise ConfigEntryNotReady("Cannot connect to the device") from e
    except NotAuthorised as e:
        raise ConfigEntryNotReady("Not authorised to connect to the device") from e
    except DeviceNotSupported as e:
        raise ConfigEntryNotReady("Device not supported") from e

    # Initialize the device
    await base_device.init()

    # if the device is a gateway, add all child devices, otherwise add the device itself.
    if base_device.is_gateway:
        # Add the gateway device to the device registry
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, base_device.serial)},
            manufacturer=MANUFACTURER,
            name=base_device.model,
            model=base_device.model,
            sw_version=base_device.fw_version,
        )

        coordinators = [
            IskraDataUpdateCoordinator(hass, child_device)
            for child_device in base_device.get_child_devices()
        ]
    else:
        coordinators = [IskraDataUpdateCoordinator(hass, base_device)]

    for coordinator in coordinators:
        await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IskraConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
