"""Support for GoodWe inverter via UDP."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging
from typing import Any

from goodwe import Inverter, Sensor, SensorKind

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    POWER_VOLT_AMPERE_REACTIVE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import DOMAIN, KEY_COORDINATOR, KEY_DEVICE_INFO, KEY_INVERTER
from .coordinator import GoodweUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Sensor name of battery SoC
BATTERY_SOC = "battery_soc"

# Sensors that are reset to 0 at midnight.
# The inverter is only powered by the solar panels and not mains power, so it goes dead when the sun goes down.
# The "_day" sensors are reset to 0 when the inverter wakes up in the morning when the sun comes up and power to the inverter is restored.
# This makes sure daily values are reset at midnight instead of at sunrise.
# When the inverter has a battery connected, HomeAssistant will not reset the values but let the inverter reset them by looking at the unavailable state of the inverter.
DAILY_RESET = ["e_day", "e_load_day"]

_MAIN_SENSORS = (
    "ppv",
    "house_consumption",
    "active_power",
    "battery_soc",
    "e_day",
    "e_total",
    "meter_e_total_exp",
    "meter_e_total_imp",
    "e_bat_charge_total",
    "e_bat_discharge_total",
)

_ICONS: dict[SensorKind, str] = {
    SensorKind.PV: "mdi:solar-power",
    SensorKind.AC: "mdi:power-plug-outline",
    SensorKind.UPS: "mdi:power-plug-off-outline",
    SensorKind.BAT: "mdi:battery-high",
    SensorKind.GRID: "mdi:transmission-tower",
}


@dataclass
class GoodweSensorEntityDescription(SensorEntityDescription):
    """Class describing Goodwe sensor entities."""

    value: Callable[
        [GoodweUpdateCoordinator, str], Any
    ] = lambda coordinator, sensor: coordinator.sensor_value(sensor)
    available: Callable[
        [GoodweUpdateCoordinator], bool
    ] = lambda coordinator: coordinator.last_update_success


_DESCRIPTIONS: dict[str, GoodweSensorEntityDescription] = {
    "A": GoodweSensorEntityDescription(
        key="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    "V": GoodweSensorEntityDescription(
        key="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    "W": GoodweSensorEntityDescription(
        key="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    "kWh": GoodweSensorEntityDescription(
        key="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda coordinator, sensor: coordinator.total_sensor_value(sensor),
        available=lambda coordinator: coordinator.data is not None,
    ),
    "VA": GoodweSensorEntityDescription(
        key="VA",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        entity_registry_enabled_default=False,
    ),
    "var": GoodweSensorEntityDescription(
        key="var",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
    ),
    "C": GoodweSensorEntityDescription(
        key="C",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "Hz": GoodweSensorEntityDescription(
        key="Hz",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
    ),
    "h": GoodweSensorEntityDescription(
        key="h",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_registry_enabled_default=False,
    ),
    "%": GoodweSensorEntityDescription(
        key="%",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
}
DIAG_SENSOR = GoodweSensorEntityDescription(
    key="_",
    state_class=SensorStateClass.MEASUREMENT,
)
TEXT_SENSOR = GoodweSensorEntityDescription(
    key="text",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the GoodWe inverter from a config entry."""
    entities: list[InverterSensor] = []
    inverter = hass.data[DOMAIN][config_entry.entry_id][KEY_INVERTER]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]
    device_info = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE_INFO]

    # Individual inverter sensors entities
    entities.extend(
        InverterSensor(coordinator, device_info, inverter, sensor)
        for sensor in inverter.sensors()
        if not sensor.id_.startswith("xx")
    )

    async_add_entities(entities)


class InverterSensor(CoordinatorEntity[GoodweUpdateCoordinator], SensorEntity):
    """Entity representing individual inverter sensor."""

    entity_description: GoodweSensorEntityDescription

    def __init__(
        self,
        coordinator: GoodweUpdateCoordinator,
        device_info: DeviceInfo,
        inverter: Inverter,
        sensor: Sensor,
    ) -> None:
        """Initialize an inverter sensor."""
        super().__init__(coordinator)
        self._attr_name = sensor.name.strip()
        self._attr_unique_id = f"{DOMAIN}-{sensor.id_}-{inverter.serial_number}"
        self._attr_device_info = device_info
        self._attr_entity_category = (
            EntityCategory.DIAGNOSTIC if sensor.id_ not in _MAIN_SENSORS else None
        )
        try:
            self.entity_description = _DESCRIPTIONS[sensor.unit]
        except KeyError:
            if "Enum" in type(sensor).__name__ or sensor.id_ == "timestamp":
                self.entity_description = TEXT_SENSOR
            else:
                self.entity_description = DIAG_SENSOR
                self._attr_native_unit_of_measurement = sensor.unit
        self._attr_icon = _ICONS.get(sensor.kind)
        # Set the inverter SoC as main device battery sensor
        if sensor.id_ == BATTERY_SOC:
            self._attr_device_class = SensorDeviceClass.BATTERY
        self._sensor = sensor
        self._stop_reset: Callable[[], None] | None = None

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        return self.entity_description.value(self.coordinator, self._sensor.id_)

    @property
    def available(self) -> bool:
        """Return if entity is available.

        We delegate the behavior to entity description lambda, since
        some sensors (like energy produced today) should report themselves
        as available even when the (non-battery) pv inverter is off-line during night
        and most of the sensors are actually unavailable.
        """
        return self.entity_description.available(self.coordinator)

    @callback
    def async_reset(self, now):
        """Reset the value back to 0 at midnight.

        Some sensors values like daily produced energy are kept available,
        even when the inverter is in sleep mode and no longer responds to request.
        In contrast to "total" sensors, these "daily" sensors need to be reset to 0 on midnight.
        """
        if not self.coordinator.last_update_success:
            self.coordinator.reset_sensor(self._sensor.id_)
            self.async_write_ha_state()
            _LOGGER.debug("Goodwe reset %s to 0", self.name)
        next_midnight = dt_util.start_of_local_day(
            dt_util.now() + timedelta(days=1, minutes=1)
        )
        self._stop_reset = async_track_point_in_time(
            self.hass, self.async_reset, next_midnight
        )

    async def async_added_to_hass(self) -> None:
        """Schedule reset task at midnight."""
        if self._sensor.id_ in DAILY_RESET:
            next_midnight = dt_util.start_of_local_day(
                dt_util.now() + timedelta(days=1)
            )
            self._stop_reset = async_track_point_in_time(
                self.hass, self.async_reset, next_midnight
            )
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Remove reset task at midnight."""
        if self._sensor.id_ in DAILY_RESET and self._stop_reset is not None:
            self._stop_reset()
        await super().async_will_remove_from_hass()
