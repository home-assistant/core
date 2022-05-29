"""Support for powerwall sensors."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # CONF_PORT,; ELECTRIC_CURRENT_AMPERE,; ELECTRIC_POTENTIAL_VOLT,
    PERCENTAGE,
    POWER_KILO_WATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=5)


# @dataclass
# class PylontechRequiredKeysMixin:
#    """Mixin for required keys."""
# key: str
# icon: str
# value_fn: Callable[float]


@dataclass
class PylontechSensorEntityDescription(
    SensorEntityDescription,
    # PylontechRequiredKeysMixin
):
    """Describes Powerwall entity."""


def _get_instant_power() -> float:
    """Get the current value in kW."""
    return 0.0


PYLONTECH_STACK_SENSORS = (
    PylontechSensorEntityDescription(
        key="TotalCapacity_Ah",
        name="Pylontech_TotalCapacity_Ah",
        state_class=SensorStateClass.MEASUREMENT,
        device_class="Capacity",
        native_unit_of_measurement="Ah",
        icon="mdi:battery"
        # value_fn=_get_instant_power,
    ),
    PylontechSensorEntityDescription(
        key="RemainCapacity_Ah",
        name="Pylontech_RemainCapacity_Ah",
        state_class=SensorStateClass.MEASUREMENT,
        device_class="Capacity",
        native_unit_of_measurement="Ah",
        icon="mdi:battery"
        # value_fn=_get_instant_power,
    ),
    PylontechSensorEntityDescription(
        key="Remain_Percent",
        name="Pylontech_Remain_Percent",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery"
        # value_fn=_get_instant_power,
    ),
    PylontechSensorEntityDescription(
        key="Power_kW",
        name="Pylontech_Power_kW",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=POWER_KILO_WATT,
        entity_registry_enabled_default=False,
        icon="mdi:battery"
        # value_fn=_get_instant_power,
    ),
    PylontechSensorEntityDescription(
        key="DischargePower_kW",
        name="Pylontech_DischargePower_kW",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=POWER_KILO_WATT,
        entity_registry_enabled_default=False,
        icon="mdi:battery"
        # value_fn=_get_instant_power,
    ),
    PylontechSensorEntityDescription(
        key="ChargePower_kW",
        name="Pylontech_ChargePower_kW",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=POWER_KILO_WATT,
        entity_registry_enabled_default=False,
        icon="mdi:battery"
        # value_fn=_get_instant_power,
    ),
    # PylontechSensorEntityDescription(
    #     key="instant_voltage",
    #     name="Average Voltage Now",
    #     state_class=SensorStateClass.MEASUREMENT,
    #     device_class=SensorDeviceClass.VOLTAGE,
    #     native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
    #     entity_registry_enabled_default=False,
    #     value_fn=_get_meter_average_voltage,
    # ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pylontech sensors."""

    entities: list[SensorEntity] = []
    entities.extend(
        PylontechStackSensor(desc, config_entry.entry_id)
        for desc in PYLONTECH_STACK_SENSORS
    )

    async_add_entities(entities)


class PylontechStackSensor(SensorEntity):
    """Representation of an Pylontech sensor."""

    def __init__(self, desc: PylontechSensorEntityDescription, entry_id: str) -> None:
        """Stack summery value."""
        self._charge = 54.321
        self._attr_name = desc.name
        self._attr_state_class = desc.state_class
        self._attr_native_unit_of_measurement = desc.native_unit_of_measurement
        self._attr_device_class = desc.device_class
        self._attr_icon = desc.icon
        self.entry_id = entry_id

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return "pylontech_stack_" + self.entry_id + "_" + str(self._attr_name)

    @property
    def native_value(self) -> float:
        """Get the current value in percentage."""
        return round(self._charge, 2)

    async def async_update(self) -> None:
        """Poll battery stack."""
        # result = await hass.async_add_executor_job(hub.update)
        self._charge = self._charge + 0.1
        if self._charge >= 100.0:
            self._charge = 0.0
