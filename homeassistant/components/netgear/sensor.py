"""Support for Netgear routers."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASS_SIGNAL_STRENGTH,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.components.device_tracker import PLATFORM_SCHEMA, SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    PERCENTAGE,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType

from .const import DEVICE_ICONS, DOMAIN
from .router import async_setup_netgear_entry, NetgearRouter, NetgearDeviceEntity

_LOGGER = logging.getLogger(__name__)

@dataclass
class NetgearSensorDescription(SensorEntityDescription):
    """Class that holds device specific info for a netgear sensor."""

    attributes: tuple = ()

SENSOR_TYPES = {
    "type": NetgearSensorDescription(
        name="link type",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    "link_rate": NetgearSensorDescription(
        name="link rate",
        native_unit_of_measurement="Mbps",
        device_class=None,
    ),
    "signal": NetgearSensorDescription(
        name="signal strength",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
    ),
}

async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up device tracker for Netgear component."""
    def generate_sensor_classes(router: NetgearRouter, device):
        sensor_classes = []
        sensor_classes.append(NetgearSensorEntity(router, device, "type"))
        sensor_classes.append(NetgearSensorEntity(router, device, "link_rate"))
        sensor_classes.append(NetgearSensorEntity(router, device, "signal"))
        return sensor_classes
    
    await async_setup_netgear_entry(hass, entry, async_add_entities, generate_sensor_classes)


class NetgearSensorEntity(NetgearDeviceEntity, SensorEntity):
    """Representation of a device connected to a Netgear router."""

    def __init__(self, router: NetgearRouter, device, attribute) -> None:
        """Initialize a Netgear device."""
        super().__init__(router, device)
        self._attribute = attribute
        self._discription = SENSOR_TYPES[self._attribute]
        self._name = f"{self.get_device_name(device)} {self._discription.name}"
        self._unique_id = f"{self._mac}-{self._attribute}"
        self._device_class = self._discription.device_class
        self._unit = self._discription.native_unit_of_measurement
        self._state = None

    @property
    def available(self):
        """Return true when state is known."""
        return self._active

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of the sensor."""
        return self._unit

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""
        self._device = self._router.devices[self._mac]
        self._active = self._device["active"]
        self._state = self._device[self._attribute]

        self.async_write_ha_state()
