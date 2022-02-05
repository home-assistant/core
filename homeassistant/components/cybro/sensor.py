"""Support for Cybro sensors."""
from __future__ import annotations

from datetime import datetime

from cybro import VarType

from homeassistant.components.sensor import (
    STATE_CLASS_TOTAL_INCREASING,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ELECTRIC_CURRENT_MILLIAMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    TIME_MILLISECONDS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    AREA_ENERGY,
    AREA_WEATHER,
    DEVICE_DESCRIPTION,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    MANUFACTURER_URL,
)
from .coordinator import CybroDataUpdateCoordinator
from .models import CybroEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cybro sensor based on a config entry."""
    coordinator: CybroDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    var_prefix = f"c{coordinator.cybro.nad}."
    # adding PLC scan time diagnostic tags
    async_add_entities(
        [
            CybroSensorEntity(
                coordinator,
                f"{var_prefix}scan_time",
                "last PLC program scan time",
                TIME_MILLISECONDS,
                VarType.INT,
                EntityCategory.DIAGNOSTIC,
            ),
            CybroSensorEntity(
                coordinator,
                f"{var_prefix}scan_time_max",
                "max. PLC program scan time",
                TIME_MILLISECONDS,
                VarType.INT,
                EntityCategory.DIAGNOSTIC,
            ),
        ]
    )

    temps = find_temperatures(coordinator)
    if temps is not None:
        async_add_entities(temps)

    # weather = find_weather(coordinator)
    # if weather is not None:
    #    async_add_entities(weather)

    power_meter = find_power_meter(coordinator)
    if power_meter is not None:

        async_add_entities(power_meter)


def find_temperatures(
    coordinator: CybroDataUpdateCoordinator,
) -> list[CybroSensorEntity] | None:
    """Find simple temperature objects in the plc vars.

    eg: c1000.th00_temperature and so on
    """
    res: list[CybroSensorEntity] = []
    dev_info = DeviceInfo(
        # entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, f"{coordinator.data.plc_info.nad}.temperatures")},
        manufacturer=MANUFACTURER,
        default_name="Temperature",
        suggested_area=AREA_WEATHER,
        model=DEVICE_DESCRIPTION,
        configuration_url=MANUFACTURER_URL,
    )
    for key in coordinator.data.plc_info.plc_vars:
        if key.find(".th") != -1 or key.find(".op") != -1:
            if key.find("_temperature") != -1:
                res.append(
                    CybroSensorEntity(
                        coordinator,
                        key,
                        "",
                        TEMP_CELSIUS,
                        VarType.FLOAT,
                        None,
                        SensorDeviceClass.TEMPERATURE,
                        0.1,
                        dev_info,
                    )
                )

    if len(res) > 0:
        return res
    return None


def find_weather(
    coordinator: CybroDataUpdateCoordinator,
) -> list[CybroSensorEntity] | None:
    """Find simple temperature objects in the plc vars.

    eg: c1000.weather_temperature and so on
    """
    res: list[CybroSensorEntity] = []
    var_prefix = f"c{coordinator.data.plc_info.nad}.weather_"
    for key in coordinator.data.plc_info.plc_vars:
        if key.find(var_prefix) != -1:
            if key.find("_temperature") != -1:
                res.append(
                    CybroSensorEntity(
                        coordinator,
                        key,
                        "",
                        TEMP_CELSIUS,
                        VarType.FLOAT,
                        None,
                        SensorDeviceClass.TEMPERATURE,
                        0.1,
                    )
                )
            elif key.find("_humidity") != -1:
                res.append(
                    CybroSensorEntity(
                        coordinator,
                        key,
                        "",
                        PERCENTAGE,
                        VarType.FLOAT,
                        None,
                        SensorDeviceClass.HUMIDITY,
                        1.0,
                    )
                )
            elif key.find("_wind_speed") != -1:
                res.append(
                    CybroSensorEntity(
                        coordinator,
                        key,
                        "",
                        SPEED_KILOMETERS_PER_HOUR,
                        VarType.FLOAT,
                        None,
                        None,
                        0.1,
                    )
                )

    if len(res) > 0:
        return res
    return None


def find_power_meter(
    coordinator: CybroDataUpdateCoordinator,
) -> list[CybroSensorEntity] | None:
    """Find power meter objects in the plc vars.

    eg: c1000.power_meter_power and so on
    """
    res: list[CybroSensorEntity] = []
    var_prefix = f"c{coordinator.data.plc_info.nad}.power_meter"

    dev_info = DeviceInfo(
        # entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, var_prefix)},
        manufacturer=MANUFACTURER,
        default_name="Cybro PLC power meter",
        suggested_area=AREA_ENERGY,
        model=DEVICE_DESCRIPTION,
        configuration_url=MANUFACTURER_URL,
    )
    for key in coordinator.data.plc_info.plc_vars:
        if key.find(var_prefix) != -1:
            if key.find("_power") != -1:
                res.append(
                    CybroSensorEntity(
                        coordinator,
                        key,
                        "",
                        POWER_WATT,
                        VarType.FLOAT,
                        None,
                        SensorDeviceClass.POWER,
                        1.0,
                        dev_info,
                    )
                )
            elif key.find("_voltage") != -1:
                res.append(
                    CybroSensorEntity(
                        coordinator,
                        key,
                        "",
                        ELECTRIC_POTENTIAL_VOLT,
                        VarType.FLOAT,
                        None,
                        SensorDeviceClass.VOLTAGE,
                        0.1,
                        dev_info,
                    )
                )
            elif key.find("_current") != -1:
                res.append(
                    CybroSensorEntity(
                        coordinator,
                        key,
                        "",
                        ELECTRIC_CURRENT_MILLIAMPERE,
                        VarType.FLOAT,
                        None,
                        SensorDeviceClass.CURRENT,
                        1.0,
                        dev_info,
                    )
                )
            elif key in (f"{var_prefix}_energy", f"{var_prefix}_energy_real"):
                res.append(
                    CybroSensorEntity(
                        coordinator,
                        key,
                        "",
                        ENERGY_KILO_WATT_HOUR,
                        VarType.FLOAT,
                        None,
                        SensorDeviceClass.ENERGY,
                        1.0,
                        dev_info,
                    )
                )
            elif key.find(f"{var_prefix}_energy_watthours") != -1:
                res.append(
                    CybroSensorEntity(
                        coordinator,
                        key,
                        "",
                        ENERGY_WATT_HOUR,
                        VarType.FLOAT,
                        None,
                        SensorDeviceClass.ENERGY,
                        1.0,
                        dev_info,
                    )
                )

    if len(res) > 0:
        return res
    return None


class CybroSensorEntity(CybroEntity, SensorEntity):
    """Defines a Cybro PLC sensor entity."""

    _var_type: VarType = VarType.INT
    _val_fact: float = 1.0

    def __init__(
        self,
        coordinator: CybroDataUpdateCoordinator,
        var_name: str = "",
        var_description: str = "",
        var_unit: str = "",
        var_type: VarType = VarType.INT,
        var_cat: EntityCategory = None,
        var_class: SensorDeviceClass = None,
        val_fact: float = 1.0,
        dev_info: DeviceInfo = None,
        # attr_icon="mdi:lightbulb",
    ) -> None:
        """Initialize a Cybro PLC sensor entity."""
        super().__init__(coordinator=coordinator)
        if var_name == "":
            return
        self._unit_of_measurement = var_unit
        self._unique_id = var_name
        self._attr_unique_id = var_name
        self._attr_name = var_description if var_description != "" else var_name
        self._state = None
        self._attr_device_info = dev_info
        self._attr_entity_category = var_cat

        self._attr_device_class = var_class
        if var_class == SensorDeviceClass.ENERGY:
            self._attr_state_class = STATE_CLASS_TOTAL_INCREASING
        LOGGER.debug(self._attr_unique_id)
        coordinator.data.add_var(self._attr_unique_id, var_type=var_type)
        self._var_type = var_type
        self._val_fact = val_fact

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of the device."""
        return self._unit_of_measurement

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        res = self.coordinator.data.vars.get(self._attr_unique_id, None)
        if res is None:
            return None
        if self._var_type == VarType.INT:
            return int(int(res.value) * self._val_fact)
        if self._var_type == VarType.FLOAT:
            return float(res.value.replace(",", "")) * self._val_fact

        return res.value

    @property
    def unique_id(self):
        """Device unique id."""
        return self._unique_id
