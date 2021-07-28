"""Support for TPLink HS100/HS110/HS200 smart switch energy sensors."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pyHS100 import SmartPlug

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    SensorEntity,
)
from homeassistant.components.switch import ATTR_TODAY_ENERGY_KWH
from homeassistant.components.tplink import SmartPlugDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ALIAS,
    CONF_DEVICE_ID,
    CONF_MAC,
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
    ATTR_TOTAL_ENERGY_KWH,
    CONF_EMETER_PARAMS,
    CONF_MODEL,
    CONF_SW_VERSION,
    CONF_SWITCH,
    COORDINATORS,
    DOMAIN as TPLINK_DOMAIN,
    ENERGY_SENSORS,
)


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
        coordinator: SmartPlugDataUpdateCoordinator = coordinators[switch.mac]
        if not switch.has_emeter and coordinator.data.get(CONF_EMETER_PARAMS) is None:
            continue
        for sensor, attributes in ENERGY_SENSORS.items():
            if coordinator.data[CONF_EMETER_PARAMS].get(sensor) is not None:
                entities.append(
                    SmartPlugSensor(switch, coordinator, sensor, attributes)
                )

    async_add_entities(entities)


class SmartPlugSensor(CoordinatorEntity, SensorEntity):
    """Representation of a TPLink Smart Plug energy sensor."""

    def __init__(
        self,
        smartplug: SmartPlug,
        coordinator: DataUpdateCoordinator,
        data_key: str,
        attributes: dict[str, str],
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.smartplug = smartplug
        self.data_key = data_key
        self._attr_unit_of_measurement = attributes[ATTR_UNIT_OF_MEASUREMENT]
        self._attr_device_class = attributes[ATTR_DEVICE_CLASS]
        self._attr_state_class = attributes[ATTR_STATE_CLASS]
        self.friendly_name = attributes[ATTR_FRIENDLY_NAME]

    @property
    def data(self) -> dict[str, Any]:
        """Return data from DataUpdateCoordinator."""
        return self.coordinator.data

    @property
    def state(self) -> float | None:
        """Return the sensors state."""
        return self.data[CONF_EMETER_PARAMS][self.data_key]

    @property
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset, if any."""
        if self.data_key in [ATTR_TODAY_ENERGY_KWH, ATTR_TOTAL_ENERGY_KWH]:
            return self.data[CONF_EMETER_PARAMS][ATTR_LAST_RESET][self.data_key]
        return None

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"{self.data[CONF_DEVICE_ID]}_{self.data_key}"

    @property
    def name(self) -> str | None:
        """Return the name of the Smart Plug energy sensor."""
        return f"{self.data[CONF_ALIAS]} {self.friendly_name}"

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
