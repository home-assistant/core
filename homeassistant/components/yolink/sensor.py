"""YoLink Binary Sensor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from yolink.client import YoLinkClient

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import percentage

from . import YoLinkCoordinator
from .const import (
    ATTR_CLIENT,
    ATTR_COORDINATOR,
    ATTR_DEVICE,
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_ID,
    ATTR_DEVICE_NAME,
    ATTR_DEVICE_TYPE,
    DOMAIN,
)
from .entity import YoLinkEntity


@dataclass
class YoLinkSensorEntityDescription(SensorEntityDescription):
    """YoLink SensorEntityDescription."""

    value: Callable = round
    supports: list[str] | None = None


SENSOR_TYPES: tuple[YoLinkSensorEntityDescription, ...] = (
    YoLinkSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        name="Battery",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: percentage.ordered_list_item_to_percentage(
            [1, 2, 3, 4], value
        ),
        supports=[ATTR_DEVICE_DOOR_SENSOR],
    ),
)

SENSOR_DEVICE_TYPE = [ATTR_DEVICE_DOOR_SENSOR]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink Sensor from a config entry."""
    sensor_devices = [
        device
        for device in hass.data[DOMAIN][config_entry.entry_id][ATTR_DEVICE]
        if device[ATTR_DEVICE_TYPE] in SENSOR_DEVICE_TYPE
    ]
    yl_client = hass.data[DOMAIN][config_entry.entry_id][ATTR_CLIENT]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][ATTR_COORDINATOR]
    entities = []
    for sensor_device in sensor_devices:
        for description in SENSOR_TYPES:
            if description.supports is None:
                continue
            if sensor_device[ATTR_DEVICE_TYPE] in description.supports:
                entities.append(
                    YoLinkSensorEntity(
                        hass, coordinator, description, sensor_device, yl_client
                    )
                )
    async_add_entities(entities)


class YoLinkSensorEntity(YoLinkEntity, SensorEntity):
    """YoLink Sensor Entity."""

    entity_description: YoLinkSensorEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: YoLinkCoordinator,
        description: YoLinkSensorEntityDescription,
        device: dict,
        client: YoLinkClient,
    ) -> None:
        """Init YoLink Sensor."""
        super().__init__(hass, coordinator, device, client)
        self.entity_description = description
        self._attr_unique_id = f"{device[ATTR_DEVICE_ID]} {self.entity_description.key}"
        self._attr_name = f"{device[ATTR_DEVICE_NAME]} ({self.entity_description.name})"

    @callback
    def update_entity_state(self, state: dict) -> None:
        """Update HA Entity State."""
        if state is None:
            return
        _attr_val = None
        if self.entity_description.value is not None:
            _attr_val = self.entity_description.value(
                state[self.entity_description.key]
            )
        else:
            _attr_val = state[self.entity_description.key]
        self._attr_native_value = _attr_val
        self.async_write_ha_state()
