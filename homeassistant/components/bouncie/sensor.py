"""Bouncie Sensors."""
from __future__ import annotations

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

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="car-info",
        icon="mdi:car",
        name="Car Info",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="car-odometer",
        icon="mdi:counter",
        name="Car Odometer",
        device_class=SensorDeviceClass.DISTANCE,
    ),
    SensorEntityDescription(
        key="car-address",
        icon="mdi:map-marker",
        name="Car Address",
    ),
    SensorEntityDescription(
        key="car-fuel",
        icon="mdi:gas-station",
        name="Car Fuel",
        device_class=SensorDeviceClass.BATTERY,
    ),
    SensorEntityDescription(
        key="car-speed",
        icon="mdi:speedometer",
        name="Car Speed",
        device_class=SensorDeviceClass.SPEED,
    ),
    SensorEntityDescription(
        key="car-mil",
        icon="mdi:engine",
        name="Car MIL",
    ),
    SensorEntityDescription(
        key="car-battery",
        icon="mdi:car-battery",
        name="Car Battery",
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

    def __init__(
        self,
        coordinator: BouncieDataUpdateCoordinator,
        description: SensorEntityDescription,
        vehicle_info: dict,
    ) -> None:
        """Init the BouncieSensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._state = None
        self._attrs: dict[str, str] = {}
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

    def _update_car_info_state(self):
        self._state = (
            "Running" if self._vehicle_info["stats"]["isRunning"] else "Not Running"
        )

    def _update_car_info_attributes(self):
        self._attrs[const.ATTR_VEHICLE_STANDARD_ENGINE_KEY] = self._vehicle_info[
            "standardEngine"
        ]
        self._attrs[const.ATTR_VEHICLE_VIN_KEY] = self._vehicle_info["vin"]
        self._attrs[const.ATTR_VEHICLE_IMEI_KEY] = self._vehicle_info["imei"]
        self._update_car_stats_attributes()

    def _update_car_odometer_state(self):
        self._state = int(self._vehicle_info["stats"]["odometer"])

    def _update_car_stats_attributes(self):
        self._attrs[const.ATTR_VEHICLE_STATS_LAST_UPDATED_KEY] = self._vehicle_info[
            "stats"
        ]["lastUpdated"]

    def _update_car_address_state(self):
        self._state = self._vehicle_info["stats"]["location"]["address"]

    def _update_car_fuel_level_state(self):
        self._state = int(self._vehicle_info["stats"]["fuelLevel"])

    def _update_car_speed_state(self):
        self._state = self._vehicle_info["stats"]["speed"]

    def _update_car_mil_state(self):
        self._state = self._vehicle_info["stats"]["mil"]["milOn"]

    def _update_car_mil_attributes(self):
        self._state = self._vehicle_info["stats"]["mil"]["lastUpdated"]

    def _update_car_battery_state(self):
        self._state = self._vehicle_info["stats"]["battery"]["status"]

    def _update_car_battery_attributes(self):
        self._attrs[const.ATTR_VEHICLE_BATTERY_LAST_UPDATED_KEY] = self._vehicle_info[
            "stats"
        ]["battery"]["lastUpdated"]

    @property
    def native_value(self) -> str | None:
        """Return state value."""
        if self.entity_description.key.startswith("car-info"):
            self._update_car_info_state()
        elif self.entity_description.key.startswith("car-odometer"):
            self._update_car_odometer_state()
        elif self.entity_description.key.startswith("car-address"):
            self._update_car_address_state()
        elif self.entity_description.key.startswith("car-fuel"):
            self._update_car_fuel_level_state()
        elif self.entity_description.key.startswith("car-speed"):
            self._update_car_speed_state()
        elif self.entity_description.key.startswith("car-mil"):
            self._update_car_mil_state()
        elif self.entity_description.key.startswith("car-battery"):
            self._update_car_battery_state()
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return state attributes."""
        if self.entity_description.key.startswith("car-info"):
            self._update_car_info_attributes()
        elif self.entity_description.key.startswith("car-mil"):
            self._update_car_mil_attributes()
        elif self.entity_description.key.startswith("car-battery"):
            self._update_car_battery_attributes()
        else:
            self._update_car_stats_attributes()
        return self._attrs
