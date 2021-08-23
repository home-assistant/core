"""Support for Goal Zero Yeti Sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    SIGNAL_STRENGTH_DECIBELS,
    TEMP_CELSIUS,
    TIME_MINUTES,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import Yeti, YetiEntity
from .const import DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="wattsIn",
        name="Watts In",
        device_class=DEVICE_CLASS_POWER,
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ampsIn",
        name="Amps In",
        device_class=DEVICE_CLASS_CURRENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="wattsOut",
        name="Watts Out",
        device_class=DEVICE_CLASS_POWER,
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ampsOut",
        name="Amps Out",
        device_class=DEVICE_CLASS_CURRENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="whOut",
        name="WH Out",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="whStored",
        name="WH Stored",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="volts",
        name="Volts",
        device_class=DEVICE_CLASS_VOLTAGE,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="socPercent",
        name="State of Charge Percent",
        device_class=DEVICE_CLASS_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="timeToEmptyFull",
        name="Time to Empty/Full",
        device_class=TIME_MINUTES,
        native_unit_of_measurement=TIME_MINUTES,
    ),
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    SensorEntityDescription(
        key="wifiStrength",
        name="Wifi Strength",
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="timestamp",
        name="Total Run Time",
        native_unit_of_measurement=TIME_SECONDS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="ssid",
        name="Wi-Fi SSID",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="ipAddr",
        name="IP Address",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Goal Zero Yeti sensor."""
    name = entry.data[CONF_NAME]
    goalzero_data = hass.data[DOMAIN][entry.entry_id]
    sensors = [
        YetiSensor(
            goalzero_data[DATA_KEY_API],
            goalzero_data[DATA_KEY_COORDINATOR],
            name,
            description,
            entry.entry_id,
        )
        for description in SENSOR_TYPES
    ]
    async_add_entities(sensors, True)


class YetiSensor(YetiEntity, SensorEntity):
    """Representation of a Goal Zero Yeti sensor."""

    def __init__(
        self,
        api: Yeti,
        coordinator: DataUpdateCoordinator,
        name: str,
        description: SensorEntityDescription,
        server_unique_id: str,
    ) -> None:
        """Initialize a Goal Zero Yeti sensor."""
        super().__init__(api, coordinator, name, server_unique_id)
        self._attr_name = f"{name} {description.name}"
        self.entity_description = description
        self._attr_unique_id = f"{server_unique_id}/{description.key}"

    @property
    def native_value(self) -> str:
        """Return the state."""
        return self.api.data.get(self.entity_description.key)
