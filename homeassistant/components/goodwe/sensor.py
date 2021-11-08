"""Support for GoodWe inverter via UDP."""
from goodwe import SensorKind
import voluptuous as vol

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
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
from homeassistant.helpers.entity import DeviceInfo
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

_DEVICE_CLASSES = {
    "A": DEVICE_CLASS_CURRENT,
    "V": DEVICE_CLASS_VOLTAGE,
    "W": DEVICE_CLASS_POWER,
    "kWh": DEVICE_CLASS_ENERGY,
    "C": DEVICE_CLASS_TEMPERATURE,
    "Hz": DEVICE_CLASS_VOLTAGE,
}

_STATE_CLASSES = {
    "A": STATE_CLASS_MEASUREMENT,
    "V": STATE_CLASS_MEASUREMENT,
    "W": STATE_CLASS_MEASUREMENT,
    "kWh": STATE_CLASS_TOTAL_INCREASING,
    "C": STATE_CLASS_MEASUREMENT,
    "Hz": STATE_CLASS_MEASUREMENT,
}

_UNITS = {
    "A": ELECTRIC_CURRENT_AMPERE,
    "V": ELECTRIC_POTENTIAL_VOLT,
    "W": POWER_WATT,
    "kWh": ENERGY_KILO_WATT_HOUR,
    "C": TEMP_CELSIUS,
    "Hz": FREQUENCY_HERTZ,
}


def _get_sensor_description(sensor):
    """Create entity description for specified inverter sensor."""
    desc = SensorEntityDescription(
        key=sensor.id_,
        name=sensor.name.strip(),
        icon=_ICONS.get(sensor.kind),
        native_unit_of_measurement=_UNITS.get(sensor.unit, sensor.unit),
        device_class=_DEVICE_CLASSES.get(sensor.unit),
        state_class=_STATE_CLASSES.get(sensor.unit),
    )
    # percentage unit on battery sensor
    if sensor.unit == "%" and sensor.kind == SensorKind.BAT:
        desc.state_class = STATE_CLASS_MEASUREMENT
        desc.device_class = DEVICE_CLASS_BATTERY

    return desc


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the GoodWe inverter from a config entry."""
    entities = []
    inverter = hass.data[DOMAIN][config_entry.entry_id][KEY_INVERTER]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    device_info: DeviceInfo = {
        "identifiers": {(DOMAIN, config_entry.unique_id)},
        "name": config_entry.title,
        "manufacturer": "GoodWe",
        "model": inverter.model_name,
        "sw_version": f"{inverter.software_version} ({inverter.arm_version})",
    }

    # Entity representing inverter itself
    inverter_entity = InverterEntity(coordinator, device_info, inverter)
    entities.append(inverter_entity)

    # Individual inverter sensors entities
    for sensor in inverter.sensors():
        if sensor.id_.startswith("xx"):
            # do not include unknown sensors
            continue
        entities.append(
            InverterSensor(
                coordinator,
                device_info,
                _get_sensor_description(sensor),
                inverter,
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

    _MAIN_ENTITY_SENSOR = "ppv"

    def __init__(self, coordinator, device_info, inverter):
        """Initialize the main inverter entity."""
        super().__init__(coordinator)
        self.entity_id = f".{DOMAIN}_inverter"
        self._attr_unique_id = f"{DOMAIN}-{inverter.serial_number}"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:solar-power"
        self._attr_name = "PV Inverter"
        self._attr_native_unit_of_measurement = POWER_WATT
        self._inverter = inverter

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
            new_value = self.coordinator.data.get(self._MAIN_ENTITY_SENSOR)
            # If no new value was provided, keep the previous
            if new_value is not None:
                self._attr_native_value = new_value

        return self._attr_native_value

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


class InverterSensor(CoordinatorEntity, SensorEntity):
    """Entity representing individual inverter sensor."""

    def __init__(self, coordinator, device_info, description, inverter):
        """Initialize an inverter sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.entity_id = f".{DOMAIN}_{description.key}"
        self._attr_unique_id = f"{DOMAIN}-{description.key}-{inverter.serial_number}"
        self._attr_device_info = device_info

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.data is not None

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        if self.coordinator.data is not None:
            new_value = self.coordinator.data.get(self.entity_description.key)
            # If no new value was provided, keep the previous
            if new_value is not None:
                # Total increasing sensor should never be set to 0
                if (
                    self.state_class == STATE_CLASS_TOTAL_INCREASING
                    and "total" in self.entity_description.key
                ):
                    if new_value:
                        self._attr_native_value = new_value
                else:
                    self._attr_native_value = new_value

        return self._attr_native_value
