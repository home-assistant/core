"""Support for Aqara binary sensors."""
from __future__ import annotations

from dataclasses import dataclass

from aqara_iot import AqaraDeviceManager, AqaraPoint

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantAqaraData
from .base import AqaraEntity, find_aqara_device_points_and_register
from .const import AQARA_BATTERY_LOW_ENTITY_NEW, AQARA_DISCOVERY_NEW, DOMAIN


@dataclass
class AqaraBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Aqara binary sensor."""

    # Value to consider binary sensor to be "on"
    on_value: str = "1"


BATTERY_STATUS_DESC = AqaraBinarySensorEntityDescription(
    key="8.0.9001",
    name="battery status",
    icon="mdi:battery",
    entity_category=EntityCategory.DIAGNOSTIC,
    on_value="1",
    device_class=BinarySensorDeviceClass.BATTERY,
)


DOOR_DESC = AqaraBinarySensorEntityDescription(  # 0: close，1:  open
    key="3.1.85",
    name="door status",
    entity_category=EntityCategory.CONFIG,
    on_value="1",
    device_class=BinarySensorDeviceClass.DOOR,
)


MOISTURE_DESC = AqaraBinarySensorEntityDescription(
    key="3.1.85",
    name="status",
    entity_category=EntityCategory.CONFIG,
    on_value="1",
    device_class=BinarySensorDeviceClass.MOISTURE,
)

BINARY_SENSORS: dict[str, tuple[AqaraBinarySensorEntityDescription, ...]] = {
    "lumi.magnet.acn002": (DOOR_DESC, BATTERY_STATUS_DESC),
    "lumi.magnet.jcn002": (DOOR_DESC, BATTERY_STATUS_DESC),
    "lumi.magnet.ac01": (DOOR_DESC, BATTERY_STATUS_DESC),
    "lumi.magnet.akr01": (DOOR_DESC, BATTERY_STATUS_DESC),
    "lumi.magnet.agl02": (DOOR_DESC, BATTERY_STATUS_DESC),
    "lumi.sensor_magnet.v1": (DOOR_DESC, BATTERY_STATUS_DESC),
    "lumi.sensor_magnet.v2": (DOOR_DESC, BATTERY_STATUS_DESC),
    "lumi.sensor_magnet.es2": (DOOR_DESC, BATTERY_STATUS_DESC),
    "lumi.sensor_magnet.aq2": (DOOR_DESC, BATTERY_STATUS_DESC),
    "lumi.flood.jcn001": (MOISTURE_DESC, BATTERY_STATUS_DESC),
    "lumi.flood.agl02": (MOISTURE_DESC, BATTERY_STATUS_DESC),
    "lumi.sensor_wleak.v1": (MOISTURE_DESC, BATTERY_STATUS_DESC),
    "lumi.sensor_wleak.es1": (MOISTURE_DESC, BATTERY_STATUS_DESC),
    "lumi.sensor_wleak.aq1": (MOISTURE_DESC, BATTERY_STATUS_DESC),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Aqara binary sensor dynamically through Aqara discovery."""
    hass_data: HomeAssistantAqaraData = hass.data[DOMAIN][entry.entry_id]

    def async_add_battery_low_entity(device_id, res_id) -> None:
        """Add battery low entity by event. call from other component."""
        aqara_point = hass_data.device_manager.device_map[device_id].point_map.get(
            hass_data.device_manager.make_point_id(device_id, res_id)
        )
        if aqara_point is not None:
            entities: list[AqaraBinarySensorEntity] = [
                AqaraBinarySensorEntity(
                    aqara_point, hass_data.device_manager, BATTERY_STATUS_DESC
                )
            ]
            async_add_entities(entities)

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Aqara binary sensor."""
        entities: list[AqaraBinarySensorEntity] = []

        def append_entity(aqara_point, description):
            entities.append(
                AqaraBinarySensorEntity(
                    aqara_point, hass_data.device_manager, description
                )
            )

        find_aqara_device_points_and_register(
            hass, hass_data, device_ids, BINARY_SENSORS, append_entity
        )
        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, AQARA_DISCOVERY_NEW, async_discover_device)
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, AQARA_BATTERY_LOW_ENTITY_NEW, async_add_battery_low_entity
        )
    )


class AqaraBinarySensorEntity(AqaraEntity, BinarySensorEntity):
    """Aqara Binary Sensor Entity."""

    entity_description: AqaraBinarySensorEntityDescription

    def __init__(
        self,
        point: AqaraPoint,
        device_manager: AqaraDeviceManager,
        description: AqaraBinarySensorEntityDescription,
    ) -> None:
        """Init Aqara binary sensor."""
        super().__init__(point, device_manager)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return (
            self.point.get_value() == self.entity_description.on_value
            or self.point.get_value() in self.entity_description.on_value
        )
