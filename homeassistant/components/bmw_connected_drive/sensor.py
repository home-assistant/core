"""Support for reading vehicle status from BMW connected drive portal."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from bimmer_connected.const import SERVICE_STATUS
from bimmer_connected.vehicle import ConnectedDriveVehicle
from bimmer_connected.vehicle_status import ChargingState

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_UNIT_SYSTEM_IMPERIAL,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PERCENTAGE,
    TIME_HOURS,
    VOLUME_GALLONS,
    VOLUME_LITERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.util.unit_system import UnitSystem

from . import (
    DOMAIN as BMW_DOMAIN,
    BMWConnectedDriveAccount,
    BMWConnectedDriveBaseEntity,
)
from .const import CONF_ACCOUNT, DATA_ENTRIES, UNIT_MAP

_LOGGER = logging.getLogger(__name__)


@dataclass
class BMWSensorEntityDescription(SensorEntityDescription):
    """Describes BMW sensor entity."""

    unit_metric: str | None = None
    unit_imperial: str | None = None


SENSOR_TYPES: dict[str, BMWSensorEntityDescription] = {
    # --- Generic ---
    "charging_time_remaining": BMWSensorEntityDescription(
        key="charging_time_remaining",
        icon="mdi:update",
        unit_metric=TIME_HOURS,
        unit_imperial=TIME_HOURS,
    ),
    "charging_status": BMWSensorEntityDescription(
        key="charging_status",
        icon="mdi:battery-charging",
    ),
    # No icon as this is dealt with directly as a special case in icon()
    "charging_level_hv": BMWSensorEntityDescription(
        key="charging_level_hv",
        unit_metric=PERCENTAGE,
        unit_imperial=PERCENTAGE,
    ),
    # --- Specific ---
    "mileage": BMWSensorEntityDescription(
        key="mileage",
        icon="mdi:speedometer",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
    ),
    "remaining_range_total": BMWSensorEntityDescription(
        key="remaining_range_total",
        icon="mdi:map-marker-distance",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
    ),
    "remaining_range_electric": BMWSensorEntityDescription(
        key="remaining_range_electric",
        icon="mdi:map-marker-distance",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
    ),
    "remaining_range_fuel": BMWSensorEntityDescription(
        key="remaining_range_fuel",
        icon="mdi:map-marker-distance",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
    ),
    "max_range_electric": BMWSensorEntityDescription(
        key="max_range_electric",
        icon="mdi:map-marker-distance",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
    ),
    "remaining_fuel": BMWSensorEntityDescription(
        key="remaining_fuel",
        icon="mdi:gas-station",
        unit_metric=VOLUME_LITERS,
        unit_imperial=VOLUME_GALLONS,
    ),
    "fuel_percent": BMWSensorEntityDescription(
        key="fuel_percent",
        icon="mdi:gas-station",
        unit_metric=PERCENTAGE,
        unit_imperial=PERCENTAGE,
    ),
}


DEFAULT_BMW_DESCRIPTION = BMWSensorEntityDescription(
    key="",
    entity_registry_enabled_default=True,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BMW ConnectedDrive sensors from config entry."""
    # pylint: disable=too-many-nested-blocks
    unit_system = hass.config.units
    account: BMWConnectedDriveAccount = hass.data[BMW_DOMAIN][DATA_ENTRIES][
        config_entry.entry_id
    ][CONF_ACCOUNT]
    entities: list[BMWConnectedDriveSensor] = []

    for vehicle in account.account.vehicles:
        for service in vehicle.available_state_services:
            if service == SERVICE_STATUS:
                entities.extend(
                    [
                        BMWConnectedDriveSensor(
                            account, vehicle, description, unit_system
                        )
                        for attribute_name in vehicle.available_attributes
                        if (description := SENSOR_TYPES.get(attribute_name))
                    ]
                )

    async_add_entities(entities, True)


class BMWConnectedDriveSensor(BMWConnectedDriveBaseEntity, SensorEntity):
    """Representation of a BMW vehicle sensor."""

    entity_description: BMWSensorEntityDescription

    def __init__(
        self,
        account: BMWConnectedDriveAccount,
        vehicle: ConnectedDriveVehicle,
        description: BMWSensorEntityDescription,
        unit_system: UnitSystem,
        service: str | None = None,
    ) -> None:
        """Initialize BMW vehicle sensor."""
        super().__init__(account, vehicle)
        self.entity_description = description

        self._service = service
        if service:
            self._attr_name = f"{vehicle.name} {service.lower()}_{description.key}"
            self._attr_unique_id = f"{vehicle.vin}-{service.lower()}-{description.key}"
        else:
            self._attr_name = f"{vehicle.name} {description.key}"
            self._attr_unique_id = f"{vehicle.vin}-{description.key}"

        if unit_system.name == CONF_UNIT_SYSTEM_IMPERIAL:
            self._attr_native_unit_of_measurement = description.unit_imperial
        else:
            self._attr_native_unit_of_measurement = description.unit_metric

    def update(self) -> None:
        """Read new state data from the library."""
        _LOGGER.debug("Updating sensors of %s", self._vehicle.name)
        vehicle_state = self._vehicle.status
        sensor_key = self.entity_description.key
        sensor_value = None

        if sensor_key == "charging_status":
            sensor_value = getattr(vehicle_state, sensor_key).value
        elif self._service is None:
            sensor_value = getattr(vehicle_state, sensor_key)

            if isinstance(sensor_value, tuple):
                sensor_unit = UNIT_MAP.get(sensor_value[1], sensor_value[1])
                sensor_value = sensor_value[0]
                sensor_value_org = sensor_value

                if self.unit_of_measurement in [LENGTH_KILOMETERS, LENGTH_MILES]:
                    sensor_value = round(
                        self.hass.config.units.length(sensor_value, sensor_unit)
                    )
                elif self.unit_of_measurement in [VOLUME_LITERS, VOLUME_GALLONS]:
                    sensor_value = round(
                        self.hass.config.units.volume(sensor_value, sensor_unit)
                    )

                _LOGGER.debug(
                    "UoM Conversion for %s. HA: %s %s, Vehicle: %s %s",
                    sensor_key,
                    sensor_value,
                    self.unit_of_measurement,
                    sensor_value_org,
                    sensor_unit,
                )

        self._attr_native_value = sensor_value

        if sensor_key == "charging_level_hv":
            charging_state = self._vehicle.status.charging_status in {
                ChargingState.CHARGING
            }
            self._attr_icon = icon_for_battery_level(
                battery_level=vehicle_state.charging_level_hv, charging=charging_state
            )
