"""Support for TPLink HS100/HS110/HS200 smart switch energy sensors."""
from __future__ import annotations

from typing import Any, Final

from pyHS100 import SmartPlug

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.components.tplink import SmartPlugDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_VOLTAGE,
    CONF_ALIAS,
    CONF_DEVICE_ID,
    CONF_MAC,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONF_EMETER_PARAMS,
    CONF_MODEL,
    CONF_SW_VERSION,
    CONF_SWITCH,
    COORDINATORS,
    DOMAIN as TPLINK_DOMAIN,
)

ATTR_CURRENT_A = "current_a"
ATTR_CURRENT_POWER_W = "current_power_w"
ATTR_TODAY_ENERGY_KWH = "today_energy_kwh"
ATTR_TOTAL_ENERGY_KWH = "total_energy_kwh"

ENERGY_SENSORS: Final[list[SensorEntityDescription]] = [
    SensorEntityDescription(
        key=ATTR_CURRENT_POWER_W,
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Current Consumption",
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_ENERGY_KWH,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Total Consumption",
    ),
    SensorEntityDescription(
        key=ATTR_TODAY_ENERGY_KWH,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Today's Consumption",
    ),
    SensorEntityDescription(
        key=ATTR_VOLTAGE,
        unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Voltage",
    ),
    SensorEntityDescription(
        key=ATTR_CURRENT_A,
        unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Current",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    entities: list[SmartPlugSensor] = []
    coordinators: list[SmartPlugDataUpdateCoordinator] = hass.data[TPLINK_DOMAIN][
        COORDINATORS
    ]
    switches: list[SmartPlug] = hass.data[TPLINK_DOMAIN][CONF_SWITCH]
    for switch in switches:
        coordinator: SmartPlugDataUpdateCoordinator = coordinators[
            switch.context or switch.mac
        ]
        if not switch.has_emeter and coordinator.data.get(CONF_EMETER_PARAMS) is None:
            continue
        for description in ENERGY_SENSORS:
            if coordinator.data[CONF_EMETER_PARAMS].get(description.key) is not None:
                entities.append(SmartPlugSensor(switch, coordinator, description))

    async_add_entities(entities)


class SmartPlugSensor(CoordinatorEntity, SensorEntity):
    """Representation of a TPLink Smart Plug energy sensor."""

    def __init__(
        self,
        smartplug: SmartPlug,
        coordinator: DataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.smartplug = smartplug
        self.entity_description = description
        self._attr_name = f"{coordinator.data[CONF_ALIAS]} {description.name}"
        self._attr_last_reset = coordinator.data[CONF_EMETER_PARAMS][
            ATTR_LAST_RESET
        ].get(description.key)

    @property
    def data(self) -> dict[str, Any]:
        """Return data from DataUpdateCoordinator."""
        return self.coordinator.data

    @property
    def state(self) -> float | None:
        """Return the sensors state."""
        return self.data[CONF_EMETER_PARAMS][self.entity_description.key]

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"{self.data[CONF_DEVICE_ID]}_{self.entity_description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return {
            "name": self.data[CONF_ALIAS],
            "model": self.data[CONF_MODEL],
            "manufacturer": "TP-Link",
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.data[CONF_MAC])},
            "sw_version": self.data[CONF_SW_VERSION],
        }
