"""Support for TPLink HS100/HS110/HS200 smart switch energy sensors."""
from __future__ import annotations

from typing import Any, Final

from kasa import SmartBulb, SmartDevice, SmartPlug

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.components.tplink import TPLinkDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_VOLTAGE,
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .common import CoordinatedTPLinkEntity
from .const import (
    CONF_EMETER_PARAMS,
    CONF_LIGHT,
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
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Current Consumption",
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_ENERGY_KWH,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        name="Total Consumption",
    ),
    SensorEntityDescription(
        key=ATTR_TODAY_ENERGY_KWH,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        name="Today's Consumption",
    ),
    SensorEntityDescription(
        key=ATTR_VOLTAGE,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Voltage",
    ),
    SensorEntityDescription(
        key=ATTR_CURRENT_A,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
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
    coordinators: list[TPLinkDataUpdateCoordinator] = hass.data[TPLINK_DOMAIN][
        COORDINATORS
    ]
    switches: list[SmartPlug] = hass.data[TPLINK_DOMAIN][CONF_SWITCH]
    lights: list[SmartBulb] = hass.data[TPLINK_DOMAIN][CONF_LIGHT]
    for dev in switches + lights:
        coordinator: TPLinkDataUpdateCoordinator = coordinators[dev.device_id]
        if not dev.has_emeter and coordinator.data.get(CONF_EMETER_PARAMS) is None:
            continue
        for description in ENERGY_SENSORS:
            if coordinator.data[CONF_EMETER_PARAMS].get(description.key) is not None:
                entities.append(SmartPlugSensor(dev, coordinator, description))

    async_add_entities(entities)


class SmartPlugSensor(CoordinatedTPLinkEntity, SensorEntity):
    """Representation of a TPLink Smart Plug energy sensor."""

    def __init__(
        self,
        device: SmartDevice,
        coordinator: DataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(device, coordinator)
        self.device = device
        self.entity_description = description

    @property
    def name(self) -> str | None:
        """Return the name of the Smart Plug.

        Overridden to include the description.
        """
        return f"{self.device.alias} {self.entity_description.name}"

    @property
    def data(self) -> dict[str, Any]:
        """Return data from DataUpdateCoordinator."""
        return self.coordinator.data

    @property
    def native_value(self) -> float | None:
        """Return the sensors state."""
        return self.data[CONF_EMETER_PARAMS][self.entity_description.key]

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"{self.device.device_id}_{self.entity_description.key}"
