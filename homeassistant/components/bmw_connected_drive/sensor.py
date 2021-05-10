"""Support for reading vehicle status from BMW connected drive portal."""
import logging
import re

from bimmer_connected.const import SERVICE_ALL_TRIPS, SERVICE_LAST_TRIP, SERVICE_STATUS
from bimmer_connected.state import ChargingState

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONF_UNIT_SYSTEM_IMPERIAL,
    DEVICE_CLASS_TIMESTAMP,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    MASS_KILOGRAMS,
    PERCENTAGE,
    TIME_HOURS,
    TIME_MINUTES,
    VOLUME_GALLONS,
    VOLUME_LITERS,
)
from homeassistant.helpers.icon import icon_for_battery_level
import homeassistant.util.dt as dt_util

from . import DOMAIN as BMW_DOMAIN, BMWConnectedDriveBaseEntity
from .const import CONF_ACCOUNT, DATA_ENTRIES

_LOGGER = logging.getLogger(__name__)

ATTR_TO_HA_METRIC = {
    # "<ID>": [<MDI_ICON>, <DEVICE_CLASS>, <UNIT_OF_MEASUREMENT>, <ENABLED_BY_DEFAULT>],
    "mileage": ["mdi:speedometer", None, LENGTH_KILOMETERS, True],
    "remaining_range_total": ["mdi:map-marker-distance", None, LENGTH_KILOMETERS, True],
    "remaining_range_electric": [
        "mdi:map-marker-distance",
        None,
        LENGTH_KILOMETERS,
        True,
    ],
    "remaining_range_fuel": ["mdi:map-marker-distance", None, LENGTH_KILOMETERS, True],
    "max_range_electric": ["mdi:map-marker-distance", None, LENGTH_KILOMETERS, True],
    "remaining_fuel": ["mdi:gas-station", None, VOLUME_LITERS, True],
    # LastTrip attributes
    "average_combined_consumption": [
        "mdi:flash",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        True,
    ],
    "average_electric_consumption": [
        "mdi:power-plug-outline",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        True,
    ],
    "average_recuperation": [
        "mdi:recycle-variant",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        True,
    ],
    "electric_distance": ["mdi:map-marker-distance", None, LENGTH_KILOMETERS, True],
    "saved_fuel": ["mdi:fuel", None, VOLUME_LITERS, False],
    "total_distance": ["mdi:map-marker-distance", None, LENGTH_KILOMETERS, True],
    # AllTrips attributes
    "average_combined_consumption_community_average": [
        "mdi:flash",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        False,
    ],
    "average_combined_consumption_community_high": [
        "mdi:flash",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        False,
    ],
    "average_combined_consumption_community_low": [
        "mdi:flash",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        False,
    ],
    "average_combined_consumption_user_average": [
        "mdi:flash",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        True,
    ],
    "average_electric_consumption_community_average": [
        "mdi:power-plug-outline",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        False,
    ],
    "average_electric_consumption_community_high": [
        "mdi:power-plug-outline",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        False,
    ],
    "average_electric_consumption_community_low": [
        "mdi:power-plug-outline",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        False,
    ],
    "average_electric_consumption_user_average": [
        "mdi:power-plug-outline",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        True,
    ],
    "average_recuperation_community_average": [
        "mdi:recycle-variant",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        False,
    ],
    "average_recuperation_community_high": [
        "mdi:recycle-variant",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        False,
    ],
    "average_recuperation_community_low": [
        "mdi:recycle-variant",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        False,
    ],
    "average_recuperation_user_average": [
        "mdi:recycle-variant",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_KILOMETERS}",
        True,
    ],
    "chargecycle_range_community_average": [
        "mdi:map-marker-distance",
        None,
        LENGTH_KILOMETERS,
        False,
    ],
    "chargecycle_range_community_high": [
        "mdi:map-marker-distance",
        None,
        LENGTH_KILOMETERS,
        False,
    ],
    "chargecycle_range_community_low": [
        "mdi:map-marker-distance",
        None,
        LENGTH_KILOMETERS,
        False,
    ],
    "chargecycle_range_user_average": [
        "mdi:map-marker-distance",
        None,
        LENGTH_KILOMETERS,
        True,
    ],
    "chargecycle_range_user_current_charge_cycle": [
        "mdi:map-marker-distance",
        None,
        LENGTH_KILOMETERS,
        True,
    ],
    "chargecycle_range_user_high": [
        "mdi:map-marker-distance",
        None,
        LENGTH_KILOMETERS,
        True
    ],
    "total_electric_distance_community_average": [
        "mdi:map-marker-distance",
        None,
        LENGTH_KILOMETERS,
        False,
    ],
    "total_electric_distance_community_high": [
        "mdi:map-marker-distance",
        None,
        LENGTH_KILOMETERS,
        False,
    ],
    "total_electric_distance_community_low": [
        "mdi:map-marker-distance",
        None,
        LENGTH_KILOMETERS,
        False,
    ],
    "total_electric_distance_user_average": [
        "mdi:map-marker-distance",
        None,
        LENGTH_KILOMETERS,
        False,
    ],
    "total_electric_distance_user_total": [
        "mdi:map-marker-distance",
        None,
        LENGTH_KILOMETERS,
        False,
    ],
    "total_saved_fuel": ["mdi:fuel", None, VOLUME_LITERS, False],
}

ATTR_TO_HA_IMPERIAL = {
    # "<ID>": [<MDI_ICON>, <DEVICE_CLASS>, <UNIT_OF_MEASUREMENT>, <ENABLED_BY_DEFAULT>],
    "mileage": ["mdi:speedometer", None, LENGTH_MILES, True],
    "remaining_range_total": ["mdi:map-marker-distance", None, LENGTH_MILES, True],
    "remaining_range_electric": ["mdi:map-marker-distance", None, LENGTH_MILES, True],
    "remaining_range_fuel": ["mdi:map-marker-distance", None, LENGTH_MILES, True],
    "max_range_electric": ["mdi:map-marker-distance", None, LENGTH_MILES, True],
    "remaining_fuel": ["mdi:gas-station", None, VOLUME_GALLONS, True],
    # LastTrip attributes
    "average_combined_consumption": [
        "mdi:flash",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        True,
    ],
    "average_electric_consumption": [
        "mdi:power-plug-outline",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        True,
    ],
    "average_recuperation": [
        "mdi:recycle-variant",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        True,
    ],
    "electric_distance": ["mdi:map-marker-distance", None, LENGTH_MILES, True],
    "saved_fuel": ["mdi:fuel", None, VOLUME_GALLONS, False],
    "total_distance": ["mdi:map-marker-distance", None, LENGTH_MILES, True],
    # AllTrips attributes
    "average_combined_consumption_community_average": [
        "mdi:flash",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        False,
    ],
    "average_combined_consumption_community_high": [
        "mdi:flash",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        False,
    ],
    "average_combined_consumption_community_low": [
        "mdi:flash",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        False,
    ],
    "average_combined_consumption_user_average": [
        "mdi:flash",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        True,
    ],
    "average_electric_consumption_community_average": [
        "mdi:power-plug-outline",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        False,
    ],
    "average_electric_consumption_community_high": [
        "mdi:power-plug-outline",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        False,
    ],
    "average_electric_consumption_community_low": [
        "mdi:power-plug-outline",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        False,
    ],
    "average_electric_consumption_user_average": [
        "mdi:power-plug-outline",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        True,
    ],
    "average_recuperation_community_average": [
        "mdi:recycle-variant",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        False,
    ],
    "average_recuperation_community_high": [
        "mdi:recycle-variant",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        False,
    ],
    "average_recuperation_community_low": [
        "mdi:recycle-variant",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        False,
    ],
    "average_recuperation_user_average": [
        "mdi:recycle-variant",
        None,
        f"{ENERGY_KILO_WATT_HOUR}/100{LENGTH_MILES}",
        True,
    ],
    "chargecycle_range_community_average": [
        "mdi:map-marker-distance",
        None,
        LENGTH_MILES,
        False,
    ],
    "chargecycle_range_community_high": [
        "mdi:map-marker-distance",
        None,
        LENGTH_MILES,
        False,
    ],
    "chargecycle_range_community_low": [
        "mdi:map-marker-distance",
        None,
        LENGTH_MILES,
        False,
    ],
    "chargecycle_range_user_average": [
        "mdi:map-marker-distance",
        None,
        LENGTH_MILES,
        True,
    ],
    "chargecycle_range_user_current_charge_cycle": [
        "mdi:map-marker-distance",
        None,
        LENGTH_MILES,
        True,
    ],
    "chargecycle_range_user_high": [
        "mdi:map-marker-distance",
        None,
        LENGTH_MILES,
        True,
    ],
    "total_electric_distance_community_average": [
        "mdi:map-marker-distance",
        None,
        LENGTH_MILES,
        False,
    ],
    "total_electric_distance_community_high": [
        "mdi:map-marker-distance",
        None,
        LENGTH_MILES,
        False,
    ],
    "total_electric_distance_community_low": [
        "mdi:map-marker-distance",
        None,
        LENGTH_MILES,
        False,
    ],
    "total_electric_distance_user_average": [
        "mdi:map-marker-distance",
        None,
        LENGTH_MILES,
        False,
    ],
    "total_electric_distance_user_total": [
        "mdi:map-marker-distance",
        None,
        LENGTH_MILES,
        False,
    ],
    "total_saved_fuel": ["mdi:fuel", None, VOLUME_GALLONS, False],
}

ATTR_TO_HA_GENERIC = {
    # "<ID>": [<MDI_ICON>, <DEVICE_CLASS>, <UNIT_OF_MEASUREMENT>, <ENABLED_BY_DEFAULT>],
    "charging_time_remaining": ["mdi:update", None, TIME_HOURS, True],
    "charging_status": ["mdi:battery-charging", None, None, True],
    # No icon as this is dealt with directly as a special case in icon()
    "charging_level_hv": [None, None, PERCENTAGE, True],
    # LastTrip attributes
    "date_utc": [None, DEVICE_CLASS_TIMESTAMP, None, True],
    "duration": ["mdi:timer-outline", None, TIME_MINUTES, True],
    "electric_distance_ratio": ["mdi:percent-outline", None, PERCENTAGE, False],
    # AllTrips attributes
    "battery_size_max": ["mdi:battery-charging-high", None, ENERGY_WATT_HOUR, False],
    "reset_date_utc": [None, DEVICE_CLASS_TIMESTAMP, None, False],
    "saved_co2": ["mdi:tree-outline", None, MASS_KILOGRAMS, False],
    "saved_co2_green_energy": ["mdi:tree-outline", None, MASS_KILOGRAMS, False],
}

ATTR_TO_HA_METRIC.update(ATTR_TO_HA_GENERIC)
ATTR_TO_HA_IMPERIAL.update(ATTR_TO_HA_GENERIC)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the BMW ConnectedDrive sensors from config entry."""
    # pylint: disable=too-many-nested-blocks
    if hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
        attribute_info = ATTR_TO_HA_IMPERIAL
    else:
        attribute_info = ATTR_TO_HA_METRIC

    account = hass.data[BMW_DOMAIN][DATA_ENTRIES][config_entry.entry_id][CONF_ACCOUNT]
    entities = []

    for vehicle in account.account.vehicles:
        for service in vehicle.available_state_services:
            if service == SERVICE_STATUS:
                for attribute_name in vehicle.drive_train_attributes:
                    if attribute_name in vehicle.available_attributes:
                        device = BMWConnectedDriveSensor(
                            account, vehicle, attribute_name, attribute_info
                        )
                        entities.append(device)
            if service == SERVICE_LAST_TRIP:
                for attribute_name in vehicle.state.last_trip.available_attributes:
                    if attribute_name == "date":
                        device = BMWConnectedDriveSensor(
                            account,
                            vehicle,
                            "date_utc",
                            attribute_info,
                            service,
                        )
                        entities.append(device)
                    else:
                        device = BMWConnectedDriveSensor(
                            account, vehicle, attribute_name, attribute_info, service
                        )
                        entities.append(device)
            if service == SERVICE_ALL_TRIPS:
                for attribute_name in vehicle.state.all_trips.available_attributes:
                    if attribute_name == "reset_date":
                        device = BMWConnectedDriveSensor(
                            account,
                            vehicle,
                            "reset_date_utc",
                            attribute_info,
                            service,
                        )
                        entities.append(device)
                    elif attribute_name in (
                        "average_combined_consumption",
                        "average_electric_consumption",
                        "average_recuperation",
                        "chargecycle_range",
                        "total_electric_distance",
                    ):
                        for attr in [
                            "community_average",
                            "community_high",
                            "community_low",
                            "user_average",
                        ]:
                            device = BMWConnectedDriveSensor(
                                account,
                                vehicle,
                                f"{attribute_name}_{attr}",
                                attribute_info,
                                service,
                            )
                            entities.append(device)
                        if attribute_name == "chargecycle_range":
                            for attr in ["user_current_charge_cycle", "user_high"]:
                                device = BMWConnectedDriveSensor(
                                    account,
                                    vehicle,
                                    f"{attribute_name}_{attr}",
                                    attribute_info,
                                    service,
                                )
                                entities.append(device)
                        if attribute_name == "total_electric_distance":
                            for attr in ["user_total"]:
                                device = BMWConnectedDriveSensor(
                                    account,
                                    vehicle,
                                    f"{attribute_name}_{attr}",
                                    attribute_info,
                                    service,
                                )
                                entities.append(device)
                    else:
                        device = BMWConnectedDriveSensor(
                            account, vehicle, attribute_name, attribute_info, service
                        )
                        entities.append(device)

    async_add_entities(entities, True)


class BMWConnectedDriveSensor(BMWConnectedDriveBaseEntity, SensorEntity):
    """Representation of a BMW vehicle sensor."""

    def __init__(self, account, vehicle, attribute: str, attribute_info, service=None):
        """Initialize BMW vehicle sensor."""
        super().__init__(account, vehicle)

        self._attribute = attribute
        self._service = service
        self._state = None
        if self._service:
            self._name = (
                f"{self._vehicle.name} {self._service.lower()}_{self._attribute}"
            )
            self._unique_id = (
                f"{self._vehicle.vin}-{self._service.lower()}-{self._attribute}"
            )
        else:
            self._name = f"{self._vehicle.name} {self._attribute}"
            self._unique_id = f"{self._vehicle.vin}-{self._attribute}"
        self._attribute_info = attribute_info

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        vehicle_state = self._vehicle.state
        charging_state = vehicle_state.charging_status in [ChargingState.CHARGING]

        if self._attribute == "charging_level_hv":
            return icon_for_battery_level(
                battery_level=vehicle_state.charging_level_hv, charging=charging_state
            )
        icon = self._attribute_info.get(self._attribute, [None, None, None, None])[0]
        return icon

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        enabled_default = self._attribute_info.get(
            self._attribute, [None, None, None, True]
        )[3]
        return enabled_default

    @property
    def state(self):
        """Return the state of the sensor.

        The return type of this call depends on the attribute that
        is configured.
        """
        return self._state

    @property
    def device_class(self) -> str:
        """Get the device class."""
        clss = self._attribute_info.get(self._attribute, [None, None, None, None])[1]
        return clss

    @property
    def unit_of_measurement(self) -> str:
        """Get the unit of measurement."""
        unit = self._attribute_info.get(self._attribute, [None, None, None, None])[2]
        return unit

    def update(self) -> None:
        """Read new state data from the library."""
        _LOGGER.debug("Updating %s", self._vehicle.name)
        vehicle_state = self._vehicle.state
        vehicle_last_trip = self._vehicle.state.last_trip
        vehicle_all_trips = self._vehicle.state.all_trips
        if self._attribute == "charging_status":
            self._state = getattr(vehicle_state, self._attribute).value
        elif self.unit_of_measurement == VOLUME_GALLONS:
            value = getattr(vehicle_state, self._attribute)
            value_converted = self.hass.config.units.volume(value, VOLUME_LITERS)
            self._state = round(value_converted)
        elif self.unit_of_measurement == LENGTH_MILES:
            value = getattr(vehicle_state, self._attribute)
            value_converted = self.hass.config.units.length(value, LENGTH_KILOMETERS)
            self._state = round(value_converted)
        elif self._service is None:
            self._state = getattr(vehicle_state, self._attribute)
        elif self._service == SERVICE_LAST_TRIP:
            if self._attribute == "date_utc":
                date_str = getattr(vehicle_last_trip, "date")
                self._state = dt_util.parse_datetime(date_str).isoformat()
            else:
                self._state = getattr(vehicle_last_trip, self._attribute)
        elif self._service == SERVICE_ALL_TRIPS:
            for attribute in [
                "average_combined_consumption",
                "average_electric_consumption",
                "average_recuperation",
                "chargecycle_range",
                "total_electric_distance",
            ]:
                match = re.search(f"({attribute})_(.+)", self._attribute)
                if match:
                    attr = getattr(vehicle_all_trips, match.group(1))
                    sub_attr = match.group(2)
                    self._state = getattr(attr, sub_attr)
                    return
            if self._attribute == "reset_date_utc":
                date_str = getattr(vehicle_all_trips, "reset_date")
                self._state = dt_util.parse_datetime(date_str).isoformat()
            else:
                self._state = getattr(vehicle_all_trips, self._attribute)
