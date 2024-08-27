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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER

PLATFORMS: list[Platform] = [Platform.SENSOR]


type IskraConfigEntry = ConfigEntry[Device]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)
TIME_TILL_UNAVAILABLE = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: IskraConfigEntry) -> bool:
    """Set up iskra device from a config entry."""
    conf = entry.data
    adapter = None

    if conf[CONF_PROTOCOL] == "Modbus TCP":
        adapter = Modbus(
            ip_address=conf[CONF_HOST],
            protocol="tcp",
            port=conf[CONF_PORT],
            modbus_address=conf[CONF_ADDRESS],
        )
    elif conf[CONF_PROTOCOL] == "Rest API":
        authentication = None
        if conf.get(CONF_USERNAME) or conf.get(CONF_PASSWORD):
            authentication = {
                "username": conf[CONF_USERNAME],
                "password": conf[CONF_PASSWORD],
            }
        adapter = RestAPI(ip_address=conf[CONF_HOST], authentication=authentication)
    else:
        _LOGGER.error(
            "Invalid protocol. Supported protocols are 'Modbus TCP' and 'Rest API'"
        )
        return False

    try:
        device = await Device.create_device(adapter)
    except DeviceConnectionError as e:
        _LOGGER.error("Cannot connect to the device: %s", e)
        return False
    except NotAuthorised as e:
        _LOGGER.error("Not authorised: %s", e)
        return False
    except DeviceNotSupported as e:
        _LOGGER.error("Device not supported: %s", e)
        return False

    await device.init()

    entry.runtime_data = device

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IskraConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class IskraDevice(Entity):
    """Representation a base Iskra device."""

    _attr_should_poll = True

    def __init__(self, device, gateway, config_entry):
        """Initialize the Iskra device."""
        self._state = None
        self._is_available = True
        self._serial = device.serial
        self._model = device.model
        self._fw_version = device.fw_version
        self._device_name = f"{self._serial}"
        self._remove_unavailability_tracker = None
        self._device = device
        self.gateway = gateway
        self._gateway_id = config_entry.unique_id

        self._is_gateway = self._device.is_gateway
        self._device_id = self._serial

    @property
    def device_id(self):
        """Return the device id of the Iskra device."""
        return self._device_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info of the Iskra Aqara device."""
        if self._is_gateway:
            device_info = DeviceInfo(
                identifiers={(DOMAIN, self._device_id)},
                manufacturer=MANUFACTURER,
                model=self._model,
                name=self._device_name,
                sw_version=self._fw_version,
                serial_number=self._serial,
            )
        else:
            device_info = DeviceInfo(
                connections={("IP", self._device_id)},
                identifiers={(DOMAIN, self._device_id)},
                manufacturer=MANUFACTURER,
                model=self._model,
                name=self._device_name,
                sw_version=self._fw_version,
                serial_number=self._serial,
                via_device=(DOMAIN, self._gateway_id),
            )

        return device_info

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.available
