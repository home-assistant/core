"""Support for GoodWe inverter via UDP."""
from goodwe import Inverter, Sensor, SensorKind
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
    ENTITY_CATEGORY_DIAGNOSTIC,
    FREQUENCY_HERTZ,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, KEY_COORDINATOR, KEY_INVERTER

# Service related constants
SERVICE_SET_WORK_MODE = "set_work_mode"
ATTR_WORK_MODE = "work_mode"
SERVICE_SET_ONGRID_BATTERY_DOD = "set_ongrid_battery_dod"
ATTR_ONGRID_BATTERY_DOD = "ongrid_battery_dod"
SERVICE_SET_GRID_EXPORT_LIMIT = "set_grid_export_limit"
ATTR_GRID_EXPORT_LIMIT = "grid_export_limit"

_MAIN_SENSORS = (
    "house_consumption",
    "active_power",
    "battery_soc",
    "e_day",
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


def _get_sensor_description(sensor: Sensor) -> SensorEntityDescription:
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

    device_info = DeviceInfo(
        configuration_url="https://www.semsportal.com",
        identifiers={(DOMAIN, config_entry.unique_id)},
        name=config_entry.title,
        manufacturer="GoodWe",
        model=inverter.model_name,
        sw_version=f"{inverter.software_version} ({inverter.arm_version})",
    )

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
        "async_set_work_mode",
    )
    platform.async_register_entity_service(
        SERVICE_SET_ONGRID_BATTERY_DOD,
        {vol.Required(ATTR_ONGRID_BATTERY_DOD): vol.Coerce(int)},
        "async_set_ongrid_battery_dod",
    )
    platform.async_register_entity_service(
        SERVICE_SET_GRID_EXPORT_LIMIT,
        {vol.Required(ATTR_GRID_EXPORT_LIMIT): vol.Coerce(int)},
        "async_set_grid_export_limit",
    )

    return True


class InverterEntity(CoordinatorEntity, SensorEntity):
    """Entity representing the inverter instance itself."""

    _MAIN_ENTITY_SENSOR = "ppv"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: DeviceInfo,
        inverter: Inverter,
    ) -> None:
        """Initialize the main inverter entity."""
        super().__init__(coordinator)
        self.entity_id = f".{DOMAIN}_inverter"
        self._attr_unique_id = f"{DOMAIN}-{inverter.serial_number}"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:solar-power"
        self._attr_name = "PV Inverter"
        self._attr_native_unit_of_measurement = POWER_WATT
        self._inverter: Inverter = inverter

    async def async_set_work_mode(self, work_mode: int) -> None:
        """Set the inverter work mode."""
        await self._inverter.set_work_mode(work_mode)

    async def async_set_ongrid_battery_dod(self, ongrid_battery_dod: int) -> None:
        """Set the on-grid battery dod."""
        await self._inverter.set_ongrid_battery_dod(ongrid_battery_dod)

    async def async_set_grid_export_limit(self, grid_export_limit: int) -> None:
        """Set the grid export limit."""
        await self._inverter.set_grid_export_limit(grid_export_limit)

    @property
    def available(self) -> bool:
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
            "serial_number": self._inverter.serial_number,
        }
        return data


class InverterSensor(CoordinatorEntity, SensorEntity):
    """Entity representing individual inverter sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: DeviceInfo,
        description: SensorEntityDescription,
        inverter: Inverter,
    ) -> None:
        """Initialize an inverter sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.entity_id = f".{DOMAIN}_{description.key}"
        self._attr_unique_id = f"{DOMAIN}-{description.key}-{inverter.serial_number}"
        self._attr_device_info = device_info
        self._attr_entity_category = (
            ENTITY_CATEGORY_DIAGNOSTIC if description.key not in _MAIN_SENSORS else None
        )

    @property
    def available(self) -> bool:
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
