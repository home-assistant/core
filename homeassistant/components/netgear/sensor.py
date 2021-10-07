"""Support for Netgear routers."""
import logging

from homeassistant.components.sensor import (
    DEVICE_CLASS_SIGNAL_STRENGTH,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType

from .router import NetgearDeviceEntity, NetgearRouter, async_setup_netgear_entry

_LOGGER = logging.getLogger(__name__)


SENSOR_TYPES = {
    "type": SensorEntityDescription(
        key="type",
        name="link type",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    "link_rate": SensorEntityDescription(
        key="link_rate",
        name="link rate",
        native_unit_of_measurement="Mbps",
        device_class=None,
    ),
    "signal": SensorEntityDescription(
        key="signal",
        name="signal strength",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
    ),
}


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for Netgear component."""

    def generate_sensor_classes(router: NetgearRouter, device: dict):
        return [
            NetgearSensorEntity(router, device, attribute)
            for attribute in ("type", "link_rate", "signal")
        ]

    async_setup_netgear_entry(hass, entry, async_add_entities, generate_sensor_classes)


class NetgearSensorEntity(NetgearDeviceEntity, SensorEntity):
    """Representation of a device connected to a Netgear router."""

    _attr_entity_registry_enabled_default = False

    def __init__(self, router: NetgearRouter, device: dict, attribute: str) -> None:
        """Initialize a Netgear device."""
        super().__init__(router, device)
        self._attribute = attribute
        self.entity_description = SENSOR_TYPES[self._attribute]
        self._name = f"{self.get_device_name()} {self.entity_description.name}"
        self._unique_id = f"{self._mac}-{self._attribute}"
        self._state = self._device[self._attribute]

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""
        self._device = self._router.devices[self._mac]
        self._active = self._device["active"]
        if self._device[self._attribute] is not None:
            self._state = self._device[self._attribute]

        self.async_write_ha_state()
