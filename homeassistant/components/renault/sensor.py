"""Support for Renault sensors."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_KILOMETERS,
    PERCENTAGE,
    POWER_KILO_WATT,
    TEMP_CELSIUS,
    TIME_MINUTES,
    VOLUME_LITERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.util import slugify

from .const import (
    DEVICE_CLASS_CHARGE_MODE,
    DEVICE_CLASS_CHARGE_STATE,
    DEVICE_CLASS_PLUG_STATE,
    DOMAIN,
)
from .renault_entities import (
    RenaultBatteryDataEntity,
    RenaultChargeModeDataEntity,
    RenaultCockpitDataEntity,
    RenaultDataEntity,
    RenaultHVACDataEntity,
)
from .renault_hub import RenaultHub
from .renault_vehicle import RenaultVehicleProxy

ATTR_BATTERY_AVAILABLE_ENERGY = "battery_available_energy"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    proxy: RenaultHub = hass.data[DOMAIN][config_entry.unique_id]
    entities = await get_entities(proxy)
    async_add_entities(entities)


async def get_entities(proxy: RenaultHub) -> list[RenaultDataEntity]:
    """Create Renault entities for all vehicles."""
    entities = []
    for vehicle in proxy.vehicles.values():
        entities.extend(await get_vehicle_entities(vehicle))
    return entities


async def get_vehicle_entities(vehicle: RenaultVehicleProxy) -> list[RenaultDataEntity]:
    """Create Renault entities for single vehicle."""
    entities: list[RenaultDataEntity] = []
    if "cockpit" in vehicle.coordinators:
        entities.append(RenaultMileageSensor(vehicle, "Mileage"))
        if vehicle.details.uses_fuel():
            entities.append(RenaultFuelAutonomySensor(vehicle, "Fuel Autonomy"))
            entities.append(RenaultFuelQuantitySensor(vehicle, "Fuel Quantity"))
    if "hvac_status" in vehicle.coordinators:
        entities.append(RenaultOutsideTemperatureSensor(vehicle, "Outside Temperature"))
    if "battery" in vehicle.coordinators:
        entities.append(RenaultBatteryLevelSensor(vehicle, "Battery Level"))
        entities.append(RenaultChargeStateSensor(vehicle, "Charge State"))
        entities.append(
            RenaultChargingRemainingTimeSensor(vehicle, "Charging Remaining Time")
        )
        entities.append(RenaultChargingPowerSensor(vehicle, "Charging Power"))
        entities.append(RenaultPlugStateSensor(vehicle, "Plug State"))
        entities.append(RenaultBatteryAutonomySensor(vehicle, "Battery Autonomy"))
        entities.append(RenaultBatteryTemperatureSensor(vehicle, "Battery Temperature"))
    if "charge_mode" in vehicle.coordinators:
        entities.append(RenaultChargeModeSensor(vehicle, "Charge Mode"))
    return entities


class RenaultBatteryAutonomySensor(RenaultBatteryDataEntity):
    """Battery autonomy sensor."""

    @property
    def state(self) -> int | None:
        """Return the state of this entity."""
        return self.data.batteryAutonomy if self.data else None

    @property
    def icon(self) -> str:
        """Icon handling."""
        return "mdi:ev-station"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return LENGTH_KILOMETERS


class RenaultBatteryLevelSensor(RenaultBatteryDataEntity):
    """Battery Level sensor."""

    @property
    def state(self) -> int | None:
        """Return the state of this entity."""
        return self.data.batteryLevel if self.data else None

    @property
    def device_class(self) -> str:
        """Return the class of this entity."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return PERCENTAGE

    @property
    def icon(self) -> str:
        """Icon handling."""
        return icon_for_battery_level(
            battery_level=self.state, charging=self.is_charging
        )

    @property
    def device_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of this entity."""
        attrs = super().device_state_attributes
        attrs[ATTR_BATTERY_AVAILABLE_ENERGY] = (
            self.data.batteryAvailableEnergy if self.data else None
        )
        return attrs


class RenaultBatteryTemperatureSensor(RenaultBatteryDataEntity):
    """Battery Temperature sensor."""

    @property
    def state(self) -> int | None:
        """Return the state of this entity."""
        return self.data.batteryTemperature if self.data else None

    @property
    def device_class(self) -> str:
        """Return the class of this entity."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return TEMP_CELSIUS


class RenaultChargeModeSensor(RenaultChargeModeDataEntity):
    """Charge Mode sensor."""

    @property
    def state(self) -> str | None:
        """Return the state of this entity."""
        return self.data.chargeMode if self.data else None

    @property
    def icon(self) -> str:
        """Icon handling."""
        if self.data and self.data.chargeMode == "schedule_mode":
            return "mdi:calendar-clock"
        return "mdi:calendar-remove"

    @property
    def device_class(self) -> str:
        """Return sensor device class."""
        return DEVICE_CLASS_CHARGE_MODE


class RenaultChargeStateSensor(RenaultBatteryDataEntity):
    """Charge State sensor."""

    @property
    def state(self) -> str | None:
        """Return the state of this entity."""
        charging_status = self.data.get_charging_status() if self.data else None
        return slugify(charging_status.name) if charging_status is not None else None

    @property
    def icon(self) -> str:
        """Icon handling."""
        return "mdi:flash" if self.is_charging else "mdi:flash-off"

    @property
    def device_class(self) -> str:
        """Return sensor device class."""
        return DEVICE_CLASS_CHARGE_STATE


class RenaultChargingRemainingTimeSensor(RenaultBatteryDataEntity):
    """Charging Remaining Time sensor."""

    @property
    def state(self) -> int | None:
        """Return the state of this entity."""
        return self.data.chargingRemainingTime if self.data else None

    @property
    def icon(self) -> str:
        """Icon handling."""
        return "mdi:timer"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return TIME_MINUTES


class RenaultChargingPowerSensor(RenaultBatteryDataEntity):
    """Charging Power sensor."""

    @property
    def state(self) -> float | None:
        """Return the state of this entity."""
        if not self.data or self.data.chargingInstantaneousPower is None:
            return None
        if self.vehicle.details.reports_charging_power_in_watts():
            # Need to convert to kilowatts
            return self.data.chargingInstantaneousPower / 1000
        return self.data.chargingInstantaneousPower

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return POWER_KILO_WATT

    @property
    def device_class(self) -> str:
        """Return sensor device class."""
        return DEVICE_CLASS_ENERGY


class RenaultFuelAutonomySensor(RenaultCockpitDataEntity):
    """Fuel autonomy sensor."""

    @property
    def state(self) -> int | None:
        """Return the state of this entity."""
        return (
            round(self.data.fuelAutonomy)
            if self.data and self.data.fuelAutonomy is not None
            else None
        )

    @property
    def icon(self) -> str:
        """Icon handling."""
        return "mdi:gas-station"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return LENGTH_KILOMETERS


class RenaultFuelQuantitySensor(RenaultCockpitDataEntity):
    """Fuel quantity sensor."""

    @property
    def state(self) -> int | None:
        """Return the state of this entity."""
        return (
            round(self.data.fuelQuantity)
            if self.data and self.data.fuelQuantity is not None
            else None
        )

    @property
    def icon(self) -> str:
        """Icon handling."""
        return "mdi:fuel"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return VOLUME_LITERS


class RenaultMileageSensor(RenaultCockpitDataEntity):
    """Mileage sensor."""

    @property
    def state(self) -> int | None:
        """Return the state of this entity."""
        return (
            round(self.data.totalMileage)
            if self.data and self.data.totalMileage is not None
            else None
        )

    @property
    def icon(self) -> str:
        """Icon handling."""
        return "mdi:sign-direction"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return LENGTH_KILOMETERS


class RenaultOutsideTemperatureSensor(RenaultHVACDataEntity):
    """HVAC Outside Temperature sensor."""

    @property
    def state(self) -> float | None:
        """Return the state of this entity."""
        return self.data.externalTemperature if self.data else None

    @property
    def device_class(self) -> str:
        """Return the class of this entity."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return TEMP_CELSIUS


class RenaultPlugStateSensor(RenaultBatteryDataEntity):
    """Plug State sensor."""

    @property
    def state(self) -> str | None:
        """Return the state of this entity."""
        plug_status = self.data.get_plug_status() if self.data else None
        return slugify(plug_status.name) if plug_status is not None else None

    @property
    def icon(self) -> str:
        """Icon handling."""
        return "mdi:power-plug" if self.is_plugged_in else "mdi:power-plug-off"

    @property
    def device_class(self) -> str:
        """Return sensor device class."""
        return DEVICE_CLASS_PLUG_STATE
