"""Sensor platform for Vevor Diesel Heater."""
from __future__ import annotations

PARALLEL_UPDATES = 1

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    EntityCategory,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VevorHeaterConfigEntry
from .const import (
    DOMAIN,
    ERROR_NAMES,
    RUNNING_MODE_NAMES,
    RUNNING_STEP_NAMES,
)
from .coordinator import VevorHeaterCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VevorHeaterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vevor Heater sensors.

    Entities are created conditionally based on the detected BLE protocol.
    Mode 0 (unknown) creates all entities as safe fallback.
    """
    coordinator = entry.runtime_data
    mode = coordinator.protocol_mode

    # Core sensors (all protocols)
    entities: list[VevorSensorBase] = [
        VevorCaseTemperatureSensor(coordinator),
        VevorCabTemperatureSensor(coordinator),
        VevorSupplyVoltageSensor(coordinator),
        VevorRunningStepSensor(coordinator),
        VevorRunningModeSensor(coordinator),
        VevorSetLevelSensor(coordinator),
        VevorAltitudeSensor(coordinator),
        VevorErrorCodeSensor(coordinator),
        # Fuel consumption sensors (computed locally, not protocol-dependent)
        VevorHourlyFuelConsumptionSensor(coordinator),
        VevorDailyFuelConsumedSensor(coordinator),
        VevorTotalFuelConsumedSensor(coordinator),
        VevorDailyFuelHistorySensor(coordinator),
        # Runtime tracking sensors (computed locally)
        VevorDailyRuntimeSensor(coordinator),
        VevorTotalRuntimeSensor(coordinator),
        VevorDailyRuntimeHistorySensor(coordinator),
        # Fuel level tracking (computed locally)
        VevorFuelRemainingSensor(coordinator),
        VevorLastRefueledSensor(coordinator),
        VevorFuelConsumedSinceResetSensor(coordinator),
    ]

    # Extended sensors (encrypted protocols + CBFF: heater_offset, CO, raw temp)
    if mode in (0, 2, 4, 6):
        entities.extend([
            VevorRawInteriorTemperatureSensor(coordinator),
            VevorHeaterOffsetSensor(coordinator),
            VevorCOSensor(coordinator),
        ])

    # CBFF-only sensors (HW/SW version, remaining run time, temp diff)
    if mode in (0, 6):
        entities.extend([
            VevorHardwareVersionSensor(coordinator),
            VevorSoftwareVersionSensor(coordinator),
            VevorRemainingRunTimeSensor(coordinator),
            VevorStartupTempDiffSensor(coordinator),
            VevorShutdownTempDiffSensor(coordinator),
        ])

    async_add_entities(entities)


class VevorSensorBase(CoordinatorEntity[VevorHeaterCoordinator], SensorEntity):
    """Base class for Vevor Heater sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VevorHeaterCoordinator,
        key: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_name = name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.native_value is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorCaseTemperatureSensor(VevorSensorBase):
    """Case temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "case_temp", "Case Temperature")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get("case_temperature")


class VevorCabTemperatureSensor(VevorSensorBase):
    """Cab/interior temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "cab_temp", "Interior Temperature")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get("cab_temperature")


class VevorRawInteriorTemperatureSensor(VevorSensorBase):
    """Raw interior temperature sensor (before any offset).

    This shows the actual temperature reading from the heater's internal
    sensor, before any offset is applied. Useful for debugging and
    understanding the offset calibration.
    """

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False  # Disabled by default

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "cab_temp_raw", "Interior Temperature (Raw)")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get("cab_temperature_raw")


class VevorHeaterOffsetSensor(VevorSensorBase):
    """Heater temperature offset sensor.

    Shows the current temperature offset that has been sent to the heater
    via BLE command 12. This offset is used by the heater's control board
    for its temperature-based auto-start/stop logic.
    """

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer-plus"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "heater_offset", "Temperature Offset")

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        return self.coordinator.data.get("heater_offset", 0)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Always available when coordinator is available (offset defaults to 0)
        return self.coordinator.last_update_success


class VevorSupplyVoltageSensor(VevorSensorBase):
    """Supply voltage sensor."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "supply_voltage", "Supply Voltage")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get("supply_voltage")


class VevorRunningStepSensor(VevorSensorBase):
    """Running step sensor."""

    _attr_icon = "mdi:progress-clock"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "running_step", "Running Step")

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        step = self.coordinator.data.get("running_step")
        return RUNNING_STEP_NAMES.get(step, f"Unknown ({step})")


class VevorRunningModeSensor(VevorSensorBase):
    """Running mode sensor."""

    _attr_icon = "mdi:cog"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "running_mode", "Running Mode")

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        mode = self.coordinator.data.get("running_mode")
        return RUNNING_MODE_NAMES.get(mode, f"Unknown ({mode})")


class VevorSetLevelSensor(VevorSensorBase):
    """Set level sensor."""

    _attr_icon = "mdi:gauge"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "set_level", "Set Level")

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        return self.coordinator.data.get("set_level")


class VevorAltitudeSensor(VevorSensorBase):
    """Altitude sensor."""

    _attr_icon = "mdi:altimeter"
    _attr_native_unit_of_measurement = "m"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "altitude", "Altitude")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get("altitude")


class VevorErrorCodeSensor(VevorSensorBase):
    """Error code sensor."""

    _attr_icon = "mdi:alert-circle"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "error_code", "Error")

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        error = self.coordinator.data.get("error_code", 0)
        return ERROR_NAMES.get(error, f"Unknown error ({error})")


# Fuel consumption sensors

class VevorHourlyFuelConsumptionSensor(VevorSensorBase):
    """Estimated hourly fuel consumption sensor (instantaneous rate)."""

    _attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
    _attr_native_unit_of_measurement = f"{UnitOfVolume.LITERS}/h"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gauge"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "est_hourly_fuel_consumption", "Estimated Hourly Fuel Consumption")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get("hourly_fuel_consumption")


class VevorDailyFuelConsumedSensor(VevorSensorBase):
    """Estimated daily fuel consumed sensor."""

    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:gas-station"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "est_daily_fuel_consumed", "Estimated Daily Fuel Consumed")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get("daily_fuel_consumed")


class VevorTotalFuelConsumedSensor(VevorSensorBase):
    """Estimated total fuel consumed sensor."""

    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:gas-station"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "est_total_fuel_consumed", "Estimated Total Fuel Consumed")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get("total_fuel_consumed")


class VevorDailyFuelHistorySensor(VevorSensorBase):
    """Estimated daily fuel consumption history sensor."""

    _attr_icon = "mdi:chart-bar"
    _attr_native_unit_of_measurement = "days"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "est_daily_fuel_history", "Estimated Daily Fuel History")

    @property
    def native_value(self) -> int | None:
        """Return the number of days in history."""
        history = self.coordinator.data.get("daily_fuel_history", {})
        return len(history)

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return the state attributes with daily consumption history."""
        history = self.coordinator.data.get("daily_fuel_history", {})

        if not history:
            return {
                "history": {},
                "days_tracked": 0,
                "total_in_history": 0.0,
            }

        # Sort history by date (newest first)
        sorted_history = dict(sorted(history.items(), reverse=True))

        return {
            "history": sorted_history,
            "days_tracked": len(sorted_history),
            "total_in_history": round(sum(sorted_history.values()), 2),
            "last_7_days": round(
                sum(v for k, v in list(sorted_history.items())[:7]), 2
            ),
            "last_30_days": round(sum(sorted_history.values()), 2),
        }


# Runtime tracking sensors

class VevorDailyRuntimeSensor(VevorSensorBase):
    """Daily runtime sensor."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "daily_runtime", "Daily Runtime")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get("daily_runtime_hours")


class VevorTotalRuntimeSensor(VevorSensorBase):
    """Total runtime sensor."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:clock-check"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "total_runtime", "Total Runtime")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get("total_runtime_hours")


class VevorDailyRuntimeHistorySensor(VevorSensorBase):
    """Daily runtime history sensor."""

    _attr_icon = "mdi:chart-timeline-variant"
    _attr_native_unit_of_measurement = "days"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "daily_runtime_history", "Daily Runtime History")

    @property
    def native_value(self) -> int | None:
        """Return the number of days in history."""
        history = self.coordinator.data.get("daily_runtime_history", {})
        return len(history)

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return the state attributes with daily runtime history."""
        history = self.coordinator.data.get("daily_runtime_history", {})

        if not history:
            return {
                "history": {},
                "days_tracked": 0,
                "total_hours_in_history": 0.0,
            }

        # Sort history by date (newest first)
        sorted_history = dict(sorted(history.items(), reverse=True))

        return {
            "history": sorted_history,
            "days_tracked": len(sorted_history),
            "total_hours_in_history": round(sum(sorted_history.values()), 2),
            "last_7_days_hours": round(
                sum(v for k, v in list(sorted_history.items())[:7]), 2
            ),
            "last_30_days_hours": round(sum(sorted_history.values()), 2),
        }


# Fuel level tracking

class VevorFuelRemainingSensor(VevorSensorBase):
    """Estimated fuel remaining sensor.

    Calculates remaining fuel based on tank capacity minus
    fuel consumed since the last refuel reset.
    """

    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:fuel"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "fuel_remaining", "Estimated Fuel Remaining")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get("fuel_remaining")

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional attributes."""
        tank_capacity = self.coordinator.data.get("tank_capacity")
        consumed = self.coordinator.data.get("fuel_consumed_since_reset", 0.0)
        remaining = self.coordinator.data.get("fuel_remaining")

        attrs = {
            "fuel_consumed_since_reset": round(consumed, 2),
        }
        if tank_capacity is not None:
            attrs["tank_capacity"] = tank_capacity
            if remaining is not None and tank_capacity > 0:
                percentage = round((remaining / tank_capacity) * 100, 1)
                attrs["fuel_remaining_percent"] = percentage

        return attrs


class VevorLastRefueledSensor(VevorSensorBase):
    """Last refueled timestamp sensor.

    Shows when the user last pressed the Reset Estimated Fuel Level button.
    Persisted across restarts.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:gas-station-outline"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "last_refueled", "Last Refueled")

    @property
    def native_value(self) -> datetime | None:
        """Return the state as datetime object."""
        ts = self.coordinator.data.get("last_refueled")
        if ts is None:
            return None
        try:
            return datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("last_refueled") is not None


class VevorFuelConsumedSinceResetSensor(VevorSensorBase):
    """Estimated fuel consumed since last refuel reset.

    Shows how much fuel has been estimated to be consumed since the user
    last pressed the Reset Estimated Fuel Remaining button. Useful for
    verifying estimation accuracy against actual fuel usage.
    """

    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:gas-station-outline"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "est_fuel_since_refuel", "Estimated Fuel Since Refuel")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get("fuel_consumed_since_reset")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("fuel_consumed_since_reset") is not None


class VevorCOSensor(VevorSensorBase):
    """Carbon monoxide (CO) sensor.

    Only available on CBFF/Sunster v2.1 protocol heaters that have
    a built-in CO sensor. Shows CO concentration in PPM.
    """

    _attr_device_class = SensorDeviceClass.CO
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:molecule-co"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "co_ppm", "Carbon Monoxide")

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data.get("co_ppm")

    @property
    def available(self) -> bool:
        """Return if entity is available (only for CBFF devices with CO sensor)."""
        return self.coordinator.data.get("co_ppm") is not None


# CBFF extended info sensors

class VevorHardwareVersionSensor(VevorSensorBase):
    """Hardware version sensor (CBFF protocol only)."""

    _attr_icon = "mdi:chip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "hardware_version", "Hardware Version")

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        return self.coordinator.data.get("hardware_version")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("hardware_version") is not None


class VevorSoftwareVersionSensor(VevorSensorBase):
    """Software version sensor (CBFF protocol only)."""

    _attr_icon = "mdi:tag"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "software_version", "Software Version")

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        return self.coordinator.data.get("software_version")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("software_version") is not None


class VevorRemainingRunTimeSensor(VevorSensorBase):
    """Remaining run time sensor (CBFF protocol only).

    Shows the heater's remaining run time countdown in minutes.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "remain_run_time", "Remaining Run Time")

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        return self.coordinator.data.get("remain_run_time")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("remain_run_time") is not None


class VevorStartupTempDiffSensor(VevorSensorBase):
    """Startup temperature difference sensor (CBFF protocol only).

    The temperature difference threshold at which the heater will auto-start.
    """

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer-chevron-up"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "startup_temp_diff", "Startup Temp Difference")

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        return self.coordinator.data.get("startup_temp_diff")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("startup_temp_diff") is not None


class VevorShutdownTempDiffSensor(VevorSensorBase):
    """Shutdown temperature difference sensor (CBFF protocol only).

    The temperature difference threshold at which the heater will auto-stop.
    """

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer-chevron-down"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "shutdown_temp_diff", "Shutdown Temp Difference")

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        return self.coordinator.data.get("shutdown_temp_diff")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("shutdown_temp_diff") is not None
