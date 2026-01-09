"""Sensor platform for Hidromotic tanks and pump."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HidromoticConfigEntry
from .const import DOMAIN, PUMP_NO_WATER, PUMP_OFF, PUMP_ON, PUMP_RECOVERY
from .coordinator import HidromoticCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HidromoticConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hidromotic sensors from a config entry."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = []

    # Add pump status sensor
    entities.append(HidromoticPumpSensor(coordinator, entry))

    # Track which tanks we've added
    added_tanks: set[int] = set()

    @callback
    def async_add_tank_sensors() -> None:
        """Add sensors for newly discovered tanks."""
        tanks = coordinator.get_tanks()
        new_entities = []

        for tank_id, tank_data in tanks.items():
            if tank_id not in added_tanks:
                added_tanks.add(tank_id)
                new_entities.append(
                    HidromoticTankLevelSensor(coordinator, entry, tank_id, tank_data)
                )

        if new_entities:
            async_add_entities(new_entities)

    # Add initial entities
    async_add_entities(entities)

    # Add initial tanks
    async_add_tank_sensors()

    # Listen for updates to add new tanks dynamically
    entry.async_on_unload(coordinator.async_add_listener(async_add_tank_sensors))


class HidromoticPumpSensor(CoordinatorEntity[HidromoticCoordinator], SensorEntity):
    """Sensor for pump status."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:pump"

    def __init__(
        self,
        coordinator: HidromoticCoordinator,
        entry: HidromoticConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_pump_status"
        self._attr_name = "Pump status"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Hidromotic",
            model="CHI Smart Mini"
            if coordinator.client.data.get("is_mini")
            else "CHI Smart",
        )

    @property
    def native_value(self) -> str:
        """Return the pump status."""
        pump = self.coordinator.get_pump()
        estado = pump.get("estado", 0)

        status_map = {
            PUMP_OFF: "off",
            PUMP_ON: "on",
            PUMP_RECOVERY: "recovery",
            PUMP_NO_WATER: "no_water",
        }
        return status_map.get(estado, f"unknown_{estado}")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        pump = self.coordinator.get_pump()
        pausa = pump.get("pausa_externa", 0)
        return {
            "paused": pausa != 0,
            "pause_type": "external"
            if pausa == 1
            else ("failure" if pausa == 2 else "none"),
        }


class HidromoticTankLevelSensor(CoordinatorEntity[HidromoticCoordinator], SensorEntity):
    """Sensor for tank level."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:water-percent"

    def __init__(
        self,
        coordinator: HidromoticCoordinator,
        entry: HidromoticConfigEntry,
        tank_id: int,
        tank_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._tank_id = tank_id
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_tank_{tank_id}_level"
        self._attr_translation_key = "tank_level"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Hidromotic",
            model="CHI Smart Mini"
            if coordinator.client.data.get("is_mini")
            else "CHI Smart",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        tanks = self.coordinator.get_tanks()
        return self._tank_id in tanks and super().available

    @property
    def native_value(self) -> str:
        """Return the tank level."""
        tanks = self.coordinator.get_tanks()
        tank = tanks.get(self._tank_id)
        if tank:
            nivel = tank.get("nivel", 0xFF)
            level_map = {
                0: "full",
                1: "empty",
                2: "sensor_fail",
                3: "level_fail",
                4: "medium",
            }
            return level_map.get(nivel, "unknown")
        return "unknown"

    @property
    def icon(self) -> str:
        """Return icon based on level."""
        value = self.native_value
        if value == "full":
            return "mdi:water"
        if value == "empty":
            return "mdi:water-off"
        if value == "medium":
            return "mdi:water-percent"
        if value in ("sensor_fail", "level_fail"):
            return "mdi:water-alert"
        return "mdi:water-percent"
