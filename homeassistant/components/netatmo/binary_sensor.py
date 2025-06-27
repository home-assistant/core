"""Support for Netatmo binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import NETATMO_CREATE_WEATHER_SENSOR
from .data_handler import NetatmoDevice
from .entity import NetatmoWeatherModuleEntity

def process_status(status: StateType) -> bool | None:
    """Process status and return boolean for display."""
    if not isinstance(status, str):
        return None
    return {
        "open": True,
        "closed": False,
    }.get(status, None)

@dataclass(frozen=True, kw_only=True)
class NetatmoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Netatmo binary sensor entity."""

    netatmo_name: str
    value_fn: Callable[[StateType], StateType] = lambda x: x


BINARY_SENSOR_TYPES: tuple[NetatmoBinarySensorEntityDescription, ...] = (
    NetatmoBinarySensorEntityDescription(

#BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
#    BinarySensorEntityDescription(
        key="reachable",
        netatmo_name="reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    NetatmoBinarySensorEntityDescription(
        key="status",
        netatmo_name="status",
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=process_status,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Netatmo binary sensors based on a config entry."""

    @callback
    def _create_weather_binary_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        async_add_entities(
            NetatmoWeatherBinarySensor(netatmo_device, description)
            for description in BINARY_SENSOR_TYPES
            if description.key in netatmo_device.device.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_WEATHER_SENSOR, _create_weather_binary_sensor_entity
        )
    )


class NetatmoWeatherBinarySensor(NetatmoWeatherModuleEntity, BinarySensorEntity):
    """Implementation of a Netatmo binary sensor."""

    def __init__(
#        self, device: NetatmoDevice, description: BinarySensorEntityDescription
        self, device: NetatmoDevice, description: NetatmoBinarySensorEntityDescription
    ) -> None:
        """Initialize a Netatmo binary sensor."""
        super().__init__(device)
        self.entity_description = description
        self._attr_unique_id = f"{self.device.entity_id}-{description.key}"

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if self.entity_description.key == "reachable":
            #self._attr_native_value = self.device.reachable
            self._attr_is_on = self.device.reachable
        elif self.entity_description.key == "status":
            value = cast(
                StateType, getattr(self.device, self.entity_description.key)
            )
            if value is not None:
                value = process_status(value)
                #value = self.entity_description.value_fn(value)
            self._attr_is_on = value

        self.async_write_ha_state()
