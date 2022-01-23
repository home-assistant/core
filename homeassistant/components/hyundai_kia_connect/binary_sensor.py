"""Sensor for Hyundai / Kia Connect integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Final

from hyundai_kia_connect_api import Vehicle

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class HyundaiKiaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A class that describes custom binary sensor entities."""

    is_on: Callable[[Vehicle], bool] | None = None
    on_icon: str | None = None
    off_icon: str | None = None


SENSOR_DESCRIPTIONS: Final[tuple[HyundaiKiaBinarySensorEntityDescription, ...]] = (
    HyundaiKiaBinarySensorEntityDescription(
        key="engine_is_running",
        name="Engine",
        is_on=lambda vehicle: vehicle.engine_is_running,
        on_icon="mdi:engine",
        off_icon="mdi:engine-off",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="defrost_is_on",
        name="Defrost",
        is_on=lambda vehicle: vehicle.defrost_is_on,
        on_icon="mdi:car-defrost-front",
        off_icon="mdi:car-defrost-front",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="steering_wheel_heater_is_on",
        name="Steering Wheel Heater",
        is_on=lambda vehicle: vehicle.steering_wheel_heater_is_on,
        on_icon="mdi:steering",
        off_icon="mdi:steering",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="back_window_heater_is_on",
        name="Back Window Heater",
        is_on=lambda vehicle: vehicle.back_window_heater_is_on,
        on_icon="mdi:car-defrost-rear",
        off_icon="mdi:car-defrost-rear",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="side_mirror_heater_is_on",
        name="Side Mirror Heater",
        is_on=lambda vehicle: vehicle.side_mirror_heater_is_on,
        on_icon="mdi:car-side",
        off_icon="mdi:car-side",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="front_left_seat_heater_is_on",
        name="Front Left Seat Heater",
        is_on=lambda vehicle: vehicle.front_left_seat_heater_is_on,
        on_icon="mdi:car-seat-heater",
        off_icon="mdi:car-seat-heater",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="front_right_seat_heater_is_on",
        name="Front Right Seat Heater",
        is_on=lambda vehicle: vehicle.front_right_seat_heater_is_on,
        on_icon="mdi:car-seat-heater",
        off_icon="mdi:car-seat-heater",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="rear_left_seat_heater_is_on",
        name="Rear Left Seat Heater",
        is_on=lambda vehicle: vehicle.rear_left_seat_heater_is_on,
        on_icon="mdi:car-seat-heater",
        off_icon="mdi:car-seat-heater",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="rear_right_seat_heater_is_on",
        name="Rear Right Seat Heater",
        is_on=lambda vehicle: vehicle.rear_right_seat_heater_is_on,
        on_icon="mdi:car-seat-heater",
        off_icon="mdi:car-seat-heater",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="is_locked",
        name="Lock",
        is_on=lambda vehicle: vehicle.is_locked,
        device_class=BinarySensorDeviceClass.LOCK,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="front_left_door_is_open",
        name="Front Left Door",
        is_on=lambda vehicle: vehicle.front_left_door_is_open,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="front_right_door_is_open",
        name="Front Right Door",
        is_on=lambda vehicle: vehicle.front_right_door_is_open,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="back_left_door_is_open",
        name="Back Left Door",
        is_on=lambda vehicle: vehicle.back_left_door_is_open,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="back_right_door_is_open",
        name="Back Right Door",
        is_on=lambda vehicle: vehicle.back_right_door_is_open,
        on_icon="mdi:car-door",
        off_icon="mdi:car-door",
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="trunk_is_open",
        name="Trunk",
        is_on=lambda vehicle: vehicle.trunk_is_open,
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
        is_on=lambda vehicle: vehicle.ev_battery_is_charging,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="ev_battery_is_plugged_in",
        name="EV Battery Plug",
        is_on=lambda vehicle: vehicle.ev_battery_is_plugged_in,
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key="fuel_level_is_low",
        name="Fuel Low Level",
        is_on=lambda vehicle: vehicle.fuel_level_is_low,
        on_icon="mdi:gas-station-off",
        off_icon="mdi:gas-station",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary_sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities: list[HyundaiKiaConnectBinarySensor] = []
    for vehicle_id in coordinator.vehicle_manager.vehicles.keys():
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        for description in SENSOR_DESCRIPTIONS:
            if getattr(vehicle, description.key, None) is not None:
                entities.append(
                    HyundaiKiaConnectBinarySensor(coordinator, description, vehicle)
                )
    async_add_entities(entities)


class HyundaiKiaConnectBinarySensor(BinarySensorEntity, HyundaiKiaConnectEntity):
    """Hyundai / Kia Connect binary sensor class."""

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        description: HyundaiKiaBinarySensorEntityDescription,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description: HyundaiKiaBinarySensorEntityDescription = description
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_{description.key}"
        self._attr_name = f"{vehicle.name} {description.name}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.entity_description.is_on is not None:
            return self.entity_description.is_on(self.vehicle)
        return None

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if (
            self.entity_description.on_icon == self.entity_description.off_icon
        ) is None:
            return BinarySensorEntity.icon
        return (
            self.entity_description.on_icon
            if self.is_on
            else self.entity_description.off_icon
        )
