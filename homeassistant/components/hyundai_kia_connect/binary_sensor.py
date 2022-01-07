"""Sensor for Hyundai / Kia Connect integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final

from hyundai_kia_connect_api import Vehicle

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .const import DOMAIN
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class HyundaiKiaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A class that describes custom binary sensor entities."""

    on_icon: str | None = None
    off_icon: str | None = None


SENSOR_DESCRIPTIONS: Final[tuple[HyundaiKiaBinarySensorEntityDescription, ...]] = (
    HyundaiKiaBinarySensorEntityDescription(
        key="engine_is_running",
        name="Engine",
        device_class=BinarySensorDeviceClass.POWER,
        on_icon="mdi:engine",
        off_icon="mdi:engine-off",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="defrost_is_on",
        name="Defrost",
        device_class=BinarySensorDeviceClass.HEAT,
        on_icon="mdi:car-defrost-front",
        off_icon="mdi:car-defrost-front",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="steering_wheel_heater_is_on",
        name="Steering Wheel Heater",
        device_class=BinarySensorDeviceClass.HEAT,
        on_icon="mdi:steering",
        off_icon="mdi:steering",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="back_window_heater_is_on",
        name="Back Window Heater",
        device_class=BinarySensorDeviceClass.HEAT,
        on_icon="mdi:car-defrost-rear",
        off_icon="mdi:car-defrost-rear",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="side_mirror_heater_is_on",
        name="Side Mirror Heater",
        device_class=BinarySensorDeviceClass.HEAT,
        on_icon="mdi:car-side",
        off_icon="mdi:car-side",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="front_left_seat_heater_is_on",
        name="Front Left Seat Heater",
        device_class=BinarySensorDeviceClass.HEAT,
        on_icon="mdi:car-seat-heater",
        off_icon="mdi:car-seat-heater",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="front_right_seat_heater_is_on",
        name="Front Right Seat Heater",
        device_class=BinarySensorDeviceClass.HEAT,
        on_icon="mdi:car-seat-heater",
        off_icon="mdi:car-seat-heater",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="rear_left_seat_heater_is_on",
        name="Rear Left Seat Heater",
        device_class=BinarySensorDeviceClass.HEAT,
        on_icon="mdi:car-seat-heater",
        off_icon="mdi:car-seat-heater",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="rear_right_seat_heater_is_on",
        name="Rear Right Seat Heater",
        device_class=BinarySensorDeviceClass.HEAT,
        on_icon="mdi:car-seat-heater",
        off_icon="mdi:car-seat-heater",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="is_locked",
        name="Lock",
        device_class=BinarySensorDeviceClass.LOCK,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="front_left_door_is_open",
        name="Front Left Door",
        device_class=BinarySensorDeviceClass.DOOR,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="front_right_door_is_open",
        name="Front Right Door",
        device_class=BinarySensorDeviceClass.DOOR,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="back_left_door_is_open",
        name="Back Left Door",
        device_class=BinarySensorDeviceClass.DOOR,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="back_right_door_is_open",
        name="Back Right Door",
        device_class=BinarySensorDeviceClass.DOOR,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="trunk_is_open",
        name="Trunk",
        device_class=BinarySensorDeviceClass.DOOR,
        on_icon="mdi:car-back",
        off_icon="mdi:car-back",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="hood_is_open",
        name="Hood",
        device_class=BinarySensorDeviceClass.DOOR,
        on_icon="mdi:car",
        off_icon="mdi:car",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="ev_battery_is_charging",
        name="EV Battery Charge",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="ev_battery_is_plugged_in",
        name="EV Battery Plug",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="fuel_level_is_low",
        name="Fuel Low Level",
        device_class=BinarySensorDeviceClass.LIGHT,
        on_icon="mdi:gas-station-off",
        off_icon="mdi:gas-station",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="data",
        name="Debug Data",
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up binary_sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities = []
    for vehicle_id in coordinator.data.vehicles.keys():
        vehicle: Vehicle = coordinator.data.vehicles[vehicle_id]
        for description in SENSOR_DESCRIPTIONS:
            if getattr(vehicle, description.key, None) is not None:
                entities.append(
                    HyundaiKiaConnectBinarySensor(coordinator, description, vehicle)
                )
    async_add_entities(entities, True)
    return True


class HyundaiKiaConnectBinarySensor(BinarySensorEntity, HyundaiKiaConnectEntity):
    """Hyundai / Kia Connect binary sensor class."""

    def __init__(
        self, coordinator, description: BinarySensorEntityDescription, vehicle: Vehicle
    ):
        """Initialize the sensor."""
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._description = description
        self._key = self._description.key
        self._attr_unique_id = f"{DOMAIN}_{vehicle.name}_{self._key}"
        self._attr_name = f"{vehicle.name} {self._description.name}"
        self._attr_device_class = self._description.device_class
        if self._key == "data":
            self._attr_extra_state_attributes = vehicle.data

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return getattr(self.vehicle, self._key)

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if (self._description.on_icon == self._description.off_icon) is None:
            return BinarySensorEntity.icon
        return self._description.on_icon if self.is_on else self._description.off_icon
