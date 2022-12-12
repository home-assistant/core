"""Bouncie Sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BouncieDataUpdateCoordinator, const

ATTRIBUTION = "Data provided by Bouncie"
PARALLEL_UPDATES = 1


@dataclass
class BouncieSensorEntityDescriptionMixin:
    """Mixing for Bouncie entity."""

    value_fn: Callable
    extra_attrs_fn: Callable


@dataclass
class BouncieSensorEntityDescription(
    SensorEntityDescription, BouncieSensorEntityDescriptionMixin
):
    """Entity description class for Bouncie sensors."""


def update_car_stats_attributes(vehicle_info):
    """Return car statistics update time."""
    return {
        const.ATTR_VEHICLE_STATS_LAST_UPDATED_KEY: vehicle_info["stats"]["lastUpdated"]
    }


def update_car_info_attributes(vehicle_info):
    """Return car information."""
    extra_attrs = {}
    extra_attrs[const.ATTR_VEHICLE_STANDARD_ENGINE_KEY] = vehicle_info["standardEngine"]
    extra_attrs[const.ATTR_VEHICLE_VIN_KEY] = vehicle_info["vin"]
    extra_attrs[const.ATTR_VEHICLE_IMEI_KEY] = vehicle_info["imei"]
    return {**extra_attrs, **update_car_stats_attributes(vehicle_info)}


SENSORS: tuple[BouncieSensorEntityDescription, ...] = (
    BouncieSensorEntityDescription(
        key="car-info",
        icon="mdi:car",
        name="Car Info",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda vehicle_info: "Running"
        if vehicle_info["stats"]["isRunning"]
        else "Not Running",
        extra_attrs_fn=update_car_info_attributes,
    ),
    BouncieSensorEntityDescription(
        key="car-odometer",
        icon="mdi:counter",
        name="Car Odometer",
        device_class=SensorDeviceClass.DISTANCE,
        value_fn=lambda vehicle_info: int(vehicle_info["stats"]["odometer"]),
        extra_attrs_fn=update_car_stats_attributes,
    ),
    BouncieSensorEntityDescription(
        key="car-address",
        icon="mdi:map-marker",
        name="Car Address",
        value_fn=lambda vehicle_info: vehicle_info["stats"]["location"]["address"],
        extra_attrs_fn=update_car_stats_attributes,
    ),
    BouncieSensorEntityDescription(
        key="car-fuel",
        icon="mdi:gas-station",
        name="Car Fuel",
        device_class=SensorDeviceClass.BATTERY,
        value_fn=lambda vehicle_info: int(vehicle_info["stats"]["fuelLevel"]),
        extra_attrs_fn=update_car_stats_attributes,
    ),
    BouncieSensorEntityDescription(
        key="car-speed",
        icon="mdi:speedometer",
        name="Car Speed",
        device_class=SensorDeviceClass.SPEED,
        value_fn=lambda vehicle_info: vehicle_info["stats"]["speed"],
        extra_attrs_fn=update_car_stats_attributes,
    ),
    BouncieSensorEntityDescription(
        key="car-mil",
        icon="mdi:engine",
        name="Car MIL",
        value_fn=lambda vehicle_info: vehicle_info["stats"]["mil"]["milOn"],
        extra_attrs_fn=lambda vehicle_info: {
            const.ATTR_VEHICLE_MIL_LAST_UPDATED_KEY: vehicle_info["stats"]["mil"][
                "lastUpdated"
            ]
        },
    ),
    BouncieSensorEntityDescription(
        key="car-battery",
        icon="mdi:car-battery",
        name="Car Battery",
        value_fn=lambda vehicle_info: vehicle_info["stats"]["battery"]["status"],
        extra_attrs_fn=lambda vehicle_info: {
            const.ATTR_VEHICLE_BATTERY_LAST_UPDATED_KEY: vehicle_info["stats"][
                "battery"
            ]["lastUpdated"]
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bouncie sensor entities based on a config entry."""
    coordinator = hass.data[const.DOMAIN][config_entry.entry_id]
    for vehicle_info in coordinator.data["vehicles"]:
        async_add_entities(
            BouncieSensor(coordinator, description, vehicle_info)
            for description in SENSORS
        )


class BouncieSensor(CoordinatorEntity[BouncieDataUpdateCoordinator], SensorEntity):
    """Bouncie sensor."""

    _attr_attribution = ATTRIBUTION
    entity_description: BouncieSensorEntityDescription

    def __init__(
        self,
        coordinator: BouncieDataUpdateCoordinator,
        description: BouncieSensorEntityDescription,
        vehicle_info: dict,
    ) -> None:
        """Init the BouncieSensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._vehicle_info = vehicle_info
        self._attr_unique_id = self.entity_description.key
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, self._vehicle_info["vin"])},
            manufacturer=self._vehicle_info[const.VEHICLE_MODEL_KEY]["make"],
            model=self._vehicle_info[const.VEHICLE_MODEL_KEY]["name"],
            name=self._vehicle_info["nickName"],
            hw_version=self._vehicle_info[const.VEHICLE_MODEL_KEY]["year"],
        )

    @property
    def native_value(self) -> str | None:
        """Return state value."""
        return self.entity_description.value_fn(self._vehicle_info)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return state attributes."""
        return self.entity_description.extra_attrs_fn(self._vehicle_info)
