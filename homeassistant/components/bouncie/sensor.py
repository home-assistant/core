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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BouncieDataUpdateCoordinator, const

ATTRIBUTION = "Data provided by Bouncie"
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bouncie sensor entities based on a config entry."""
    coordinator = hass.data[const.DOMAIN][config_entry.entry_id]
    vehicles = coordinator.data["vehicles"]
    sensor_types: list[SensorEntityDescription] = []
    for vehicle in vehicles:
        sensor_types.append(
            SensorEntityDescription(
                key=f"car-info-{vehicle[const.VEHICLE_VIN_KEY]}",
                icon="mdi:car",
                name=f"{vehicle[const.VEHICLE_NICKNAME_KEY]}",
                state_class=SensorStateClass.MEASUREMENT,
            )
        )
        sensor_types.append(
            SensorEntityDescription(
                key=f"car-odometer-{vehicle[const.VEHICLE_VIN_KEY]}",
                icon="mdi:counter",
                name=f"{vehicle[const.VEHICLE_NICKNAME_KEY]} Odometer",
                device_class=SensorDeviceClass.DISTANCE,
            )
        )
        sensor_types.append(
            SensorEntityDescription(
                key=f"car-address-{vehicle[const.VEHICLE_VIN_KEY]}",
                icon="mdi:map-marker",
                name=f"{vehicle[const.VEHICLE_NICKNAME_KEY]} Address",
            )
        )
        sensor_types.append(
            SensorEntityDescription(
                key=f"car-fuel-{vehicle[const.VEHICLE_VIN_KEY]}",
                icon="mdi:gas-station",
                name=f"{vehicle[const.VEHICLE_NICKNAME_KEY]} Fuel",
                device_class=SensorDeviceClass.BATTERY,
            )
        )
        sensor_types.append(
            SensorEntityDescription(
                key=f"car-speed-{vehicle[const.VEHICLE_VIN_KEY]}",
                icon="mdi:speedometer",
                name=f"{vehicle[const.VEHICLE_NICKNAME_KEY]} Speed",
                device_class=SensorDeviceClass.SPEED,
            )
        )
        sensor_types.append(
            SensorEntityDescription(
                key=f"car-mil-{vehicle[const.VEHICLE_VIN_KEY]}",
                icon="mdi:engine",
                name=f"{vehicle[const.VEHICLE_NICKNAME_KEY]} MIL",
            )
        )
        sensor_types.append(
            SensorEntityDescription(
                key=f"car-battery-{vehicle[const.VEHICLE_VIN_KEY]}",
                icon="mdi:car-battery",
                name=f"{vehicle[const.VEHICLE_NICKNAME_KEY]} Battery",
            )
        )

    async_add_entities(
        BouncieSensor(coordinator, description) for description in sensor_types
    )


class BouncieSensor(CoordinatorEntity[BouncieDataUpdateCoordinator], SensorEntity):
    """Bouncie sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: BouncieDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Init the BouncieSensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._state = None
        self._attrs: dict[str, str] = {}
        self._attr_unique_id = f"{coordinator._client_id}-{description.key.lower()}"
        self._vehicle_info = next(
            v
            for v in self.coordinator.data["vehicles"]
            if v["vin"] == self.entity_description.key.split("-")[-1]
        )

    def _update_car_info_state(self):
        self._state = (
            "Running" if self._vehicle_info["stats"]["isRunning"] else "Not Running"
        )

    def _update_car_info_attributes(self):
        self._attrs[const.ATTR_VEHICLE_MODEL_MAKE_KEY] = self._vehicle_info[
            const.VEHICLE_MODEL_KEY
        ]["make"]
        self._attrs[const.ATTR_VEHICLE_MODEL_NAME_KEY] = self._vehicle_info[
            const.VEHICLE_MODEL_KEY
        ]["name"]
        self._attrs[const.ATTR_VEHICLE_MODEL_YEAR_KEY] = self._vehicle_info[
            const.VEHICLE_MODEL_KEY
        ]["year"]
        self._attrs[const.ATTR_VEHICLE_NICKNAME_KEY] = self._vehicle_info["nickName"]
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
        if self.entity_description.key.startswith("car-info-"):
            self._update_car_info_state()
        elif self.entity_description.key.startswith("car-odometer-"):
            self._update_car_odometer_state()
        elif self.entity_description.key.startswith("car-address-"):
            self._update_car_address_state()
        elif self.entity_description.key.startswith("car-fuel-"):
            self._update_car_fuel_level_state()
        elif self.entity_description.key.startswith("car-speed-"):
            self._update_car_speed_state()
        elif self.entity_description.key.startswith("car-mil-"):
            self._update_car_mil_state()
        elif self.entity_description.key.startswith("car-battery-"):
            self._update_car_battery_state()
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return state attributes."""
        if self.entity_description.key.startswith("car-info-"):
            self._update_car_info_attributes()
        elif self.entity_description.key.startswith("car-mil-"):
            self._update_car_mil_attributes()
        elif self.entity_description.key.startswith("car-battery-"):
            self._update_car_battery_attributes()
        else:
            self._update_car_stats_attributes()
        return self._attrs
