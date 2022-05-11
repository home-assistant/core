"""Support for Aqara binary sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    on_value: Any = True
    on_icon: str = "mdi:restart"
    off_icon: str = "mdi:restart"

    def set_key(self, key) -> AqaraBinarySensorEntityDescription:
        """Set key of binary Description."""
        self.key = key
        return self

    def set_name(self, name) -> AqaraBinarySensorEntityDescription:
        """Set name of binary Description."""
        self.name = name
        return self

    def set_icon(
        self, default_icon: str, on_icon: str, off_icon: str
    ) -> AqaraBinarySensorEntityDescription:
        """Set name of binary Description."""
        self.icon = default_icon
        self.on_icon = on_icon
        self.off_icon = off_icon
        return self


battery_staus_desc = AqaraBinarySensorEntityDescription(
    key="8.0.9001",
    name="status",
    icon="mdi:battery",
    entity_category=EntityCategory.DIAGNOSTIC,
    on_value="1",
    device_class=BinarySensorDeviceClass.BATTERY,
)


motion_desc = AqaraBinarySensorEntityDescription(
    key="3.1.85",
    name="motion",
    icon="mdi:account-switch",
    entity_category=EntityCategory.CONFIG,
    on_value="1",
    device_class=BinarySensorDeviceClass.MOTION,
)

# motion sensor
occupancy_desc = (
    AqaraBinarySensorEntityDescription(  # 1 means motion detected, 0 means no motion
        key="3.51.85",
        name="occupancy",
        icon="mdi:account-question",
        entity_category=EntityCategory.CONFIG,
        on_value="1",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    )
)

door_desc = AqaraBinarySensorEntityDescription(  # 0: close，1:  open
    key="3.1.85",
    name="status",
    icon="mdi:restart",
    entity_category=EntityCategory.CONFIG,
    on_value="1",
    device_class=BinarySensorDeviceClass.DOOR,
)


flood_desc = AqaraBinarySensorEntityDescription(
    key="3.1.85",
    name="status",
    icon="mdi:restart",
    entity_category=EntityCategory.CONFIG,
    on_value="1",
    device_class=BinarySensorDeviceClass.MOISTURE,
)


BINARY_SENSORS: dict[str, tuple[AqaraBinarySensorEntityDescription, ...]] = {
    "lumi.motion.jcn001": (motion_desc, battery_staus_desc),
    "lumi.motion.ac02": (motion_desc, battery_staus_desc),
    "lumi.motion.ac01": (occupancy_desc, battery_staus_desc),
    "lumi.motion.agl04": (motion_desc, battery_staus_desc),
    "lumi.motion.akr01": (motion_desc, battery_staus_desc),
    "lumi.motion.agl02": (motion_desc, battery_staus_desc),
    "lumi.sensor_motion.es2": (motion_desc, battery_staus_desc),
    "lumi.sensor_motion.aq2": (motion_desc, battery_staus_desc),
    "lumi.sensor_motion.v2": (motion_desc, battery_staus_desc),
    "lumi.sensor_motion.v1": (motion_desc, battery_staus_desc),
    #############################################################
    "lumi.magnet.acn002": (door_desc, battery_staus_desc),
    "lumi.magnet.jcn002": (door_desc, battery_staus_desc),
    "lumi.magnet.ac01": (door_desc, battery_staus_desc),
    "lumi.magnet.akr01": (door_desc, battery_staus_desc),
    "lumi.magnet.agl02": (door_desc, battery_staus_desc),
    "lumi.sensor_magnet.v1": (door_desc, battery_staus_desc),
    "lumi.sensor_magnet.v2": (door_desc, battery_staus_desc),
    "lumi.sensor_magnet.es2": (door_desc, battery_staus_desc),
    "lumi.sensor_magnet.aq2": (door_desc, battery_staus_desc),
    ##############################################################
    "lumi.flood.jcn001": (flood_desc, battery_staus_desc),
    "lumi.flood.agl02": (flood_desc, battery_staus_desc),
    "lumi.sensor_wleak.v1": (flood_desc, battery_staus_desc),
    "lumi.sensor_wleak.es1": (flood_desc, battery_staus_desc),
    "lumi.sensor_wleak.aq1": (flood_desc, battery_staus_desc),
    #############################################################
    # lock power
    "aqara.lock.acn008": (battery_staus_desc,),
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
                    aqara_point, hass_data.device_manager, battery_staus_desc
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
            hass, entry.entry_id, hass_data, device_ids, BINARY_SENSORS, append_entity
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

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if hasattr(self, "_attr_icon"):
            return self._attr_icon
        if hasattr(self, "entity_description"):
            if self.is_on is True and self.entity_description.on_icon != "":
                return self.entity_description.on_icon
            if self.is_on is False and self.entity_description.off_icon != "":
                return self.entity_description.off_icon

            return self.entity_description.icon
        return None
