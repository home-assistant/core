"""Support for GoodWe inverter via UDP."""
from goodwe import SensorKind
import voluptuous as vol

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KEY_COORDINATOR, KEY_INVERTER

# Service related constants
SERVICE_SET_WORK_MODE = "set_work_mode"
ATTR_WORK_MODE = "work_mode"
SET_WORK_MODE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_WORK_MODE): cv.positive_int,
    }
)
SERVICE_SET_ONGRID_BATTERY_DOD = "set_ongrid_battery_dod"
ATTR_ONGRID_BATTERY_DOD = "ongrid_battery_dod"
SET_ONGRID_BATTERY_DOD_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ONGRID_BATTERY_DOD): cv.positive_int,
    }
)
SERVICE_SET_GRID_EXPORT_LIMIT = "set_grid_export_limit"
ATTR_GRID_EXPORT_LIMIT = "grid_export_limit"
SET_GRID_EXPORT_LIMIT_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_GRID_EXPORT_LIMIT): cv.positive_int,
    }
)

_ICONS = {
    SensorKind.PV: "mdi:solar-power",
    SensorKind.AC: "mdi:power-plug-outline",
    SensorKind.UPS: "mdi:power-plug-off-outline",
    SensorKind.BAT: "mdi:battery-high",
    SensorKind.GRID: "mdi:transmission-tower",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the GoodWe inverter from a config entry."""
    entities = []
    inverter = hass.data[DOMAIN][config_entry.entry_id][KEY_INVERTER]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    # Entity representing inverter itself
    uid = f"{DOMAIN}-{inverter.serial_number}"
    inverter_entity = InverterEntity(coordinator, inverter, uid, config_entry)
    entities.append(inverter_entity)

    # Individual inverter sensors entities
    for sensor in inverter.sensors():
        if sensor.id_.startswith("xx"):
            # do not include unknown sensors
            continue
        uid = f"{DOMAIN}-{sensor.id_}-{inverter.serial_number}"
        entities.append(
            InverterSensor(
                coordinator,
                inverter,
                uid,
                config_entry,
                sensor.id_,
                sensor.name,
                sensor.unit,
                sensor.kind,
            )
        )

    async_add_entities(entities)

    # Add services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_WORK_MODE,
        {vol.Required(ATTR_WORK_MODE): vol.Coerce(int)},
        "set_work_mode",
    )
    platform.async_register_entity_service(
        SERVICE_SET_ONGRID_BATTERY_DOD,
        {vol.Required(ATTR_ONGRID_BATTERY_DOD): vol.Coerce(int)},
        "set_ongrid_battery_dod",
    )
    platform.async_register_entity_service(
        SERVICE_SET_GRID_EXPORT_LIMIT,
        {vol.Required(ATTR_GRID_EXPORT_LIMIT): vol.Coerce(int)},
        "set_grid_export_limit",
    )

    return True


class InverterEntity(CoordinatorEntity, SensorEntity):
    """Entity representing the inverter instance itself."""

    def __init__(self, coordinator, inverter, uid, config_entry):
        """Initialize the main inverter entity."""
        super().__init__(coordinator)
        self._attr_icon = "mdi:solar-power"
        self._attr_native_value = None
        self._attr_name = "PV Inverter"

        self._inverter = inverter
        self._config_entry = config_entry
        self._attr_unique_id = uid
        self.entity_id = f".{DOMAIN}_inverter"
        self._sensor = "ppv"

    async def set_work_mode(self, work_mode: int):
        """Set the inverter work mode."""
        await self._inverter.set_work_mode(work_mode)

    async def set_ongrid_battery_dod(self, ongrid_battery_dod: int):
        """Set the on-grid battery dod."""
        await self._inverter.set_ongrid_battery_dod(ongrid_battery_dod)

    async def set_grid_export_limit(self, grid_export_limit: int):
        """Set the grid export limit."""
        await self._inverter.set_grid_export_limit(grid_export_limit)

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.data is not None

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        if self.coordinator.data is not None:
            new_value = self.coordinator.data.get(self._sensor)
            # If no new value was provided, keep the previous
            if new_value is not None:
                self._attr_native_value = new_value

        return self._attr_native_value

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return POWER_WATT

    @property
    def state_attributes(self):
        """Return the inverter state attributes."""
        return self.coordinator.data

    @property
    def extra_state_attributes(self):
        """Return the inverter state attributes."""
        data = {
            "model": self._inverter.model_name,
            "serial_number": self._inverter.serial_number,
            "firmware_version": self._inverter.software_version,
            "arm_version": self._inverter.arm_version,
        }
        return data

    @property
    def device_info(self):
        """Return device info."""
        return {
            "name": self._config_entry.title,
            "identifiers": {(DOMAIN, self._config_entry.unique_id)},
            "model": self._inverter.model_name,
            "manufacturer": "GoodWe",
            "sw_version": f"{self._inverter.software_version} ({self._inverter.arm_version})",
        }


class InverterSensor(CoordinatorEntity, SensorEntity):
    """Class for a sensor."""

    def __init__(
        self,
        coordinator,
        inverter,
        uid,
        config_entry,
        sensor_id,
        sensor_name,
        unit,
        kind,
    ):
        """Initialize an inverter sensor."""
        super().__init__(coordinator)
        if kind is not None:
            self._attr_icon = _ICONS.get(kind)
        self._attr_name = sensor_name.strip()
        self._attr_native_value = None
        self._config_entry = config_entry
        self._inverter = inverter

        self._attr_unique_id = uid
        self.entity_id = f".{DOMAIN}_{sensor_id}"
        self._sensor_id = sensor_id
        if unit == "A":
            self._unit = ELECTRIC_CURRENT_AMPERE
            self._attr_state_class = STATE_CLASS_MEASUREMENT
            self._attr_device_class = DEVICE_CLASS_CURRENT
        elif unit == "V":
            self._unit = ELECTRIC_POTENTIAL_VOLT
            self._attr_state_class = STATE_CLASS_MEASUREMENT
            self._attr_device_class = DEVICE_CLASS_VOLTAGE
        elif unit == "W":
            self._unit = POWER_WATT
            self._attr_state_class = STATE_CLASS_MEASUREMENT
            self._attr_device_class = DEVICE_CLASS_POWER
        elif unit == "kWh":
            self._unit = ENERGY_KILO_WATT_HOUR
            self._attr_state_class = STATE_CLASS_TOTAL_INCREASING
            self._attr_device_class = DEVICE_CLASS_ENERGY
        elif unit == "%" and kind == SensorKind.BAT:
            self._unit = unit
            self._attr_state_class = STATE_CLASS_MEASUREMENT
            self._attr_device_class = DEVICE_CLASS_BATTERY
        elif unit == "C":
            self._unit = TEMP_CELSIUS
            self._attr_state_class = STATE_CLASS_MEASUREMENT
            self._attr_device_class = DEVICE_CLASS_TEMPERATURE
        elif unit == "Hz":
            self._unit = FREQUENCY_HERTZ
            self._attr_state_class = STATE_CLASS_MEASUREMENT
            self._attr_device_class = DEVICE_CLASS_VOLTAGE
        else:
            self._unit = unit if unit else None
            self._attr_state_class = None
            self._attr_device_class = None

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.data is not None

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        if self.coordinator.data is not None:
            new_value = self.coordinator.data.get(self._sensor_id)
            # If no new value was provided, keep the previous
            if new_value is not None:
                # Total increasing sensor should never be set to 0
                if (
                    self._attr_state_class == STATE_CLASS_TOTAL_INCREASING
                    and "total" in self._sensor_id
                ):
                    if new_value:
                        self._attr_native_value = new_value
                else:
                    self._attr_native_value = new_value

        return self._attr_native_value

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_info(self):
        """Return device info."""
        return {
            "name": self._config_entry.title,
            "identifiers": {(DOMAIN, self._config_entry.unique_id)},
            "model": self._inverter.model_name,
            "manufacturer": "GoodWe",
            "sw_version": f"{self._inverter.software_version} ({self._inverter.arm_version})",
        }
