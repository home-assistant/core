"""Binary sensor platform for Hidromotic tanks."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HidromoticConfigEntry
from .const import DOMAIN, TANK_EMPTY, TANK_FULL
from .coordinator import HidromoticCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HidromoticConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hidromotic binary sensors from a config entry."""
    coordinator = entry.runtime_data

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
                # Add both "full" and "empty" sensors for each tank
                new_entities.append(
                    HidromoticTankFullSensor(coordinator, entry, tank_id, tank_data)
                )
                new_entities.append(
                    HidromoticTankEmptySensor(coordinator, entry, tank_id, tank_data)
                )

        if new_entities:
            async_add_entities(new_entities)

    # Add initial tanks
    async_add_tank_sensors()

    # Listen for updates to add new tanks dynamically
    entry.async_on_unload(coordinator.async_add_listener(async_add_tank_sensors))


class HidromoticTankFullSensor(
    CoordinatorEntity[HidromoticCoordinator], BinarySensorEntity
):
    """Binary sensor for tank full status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.MOISTURE

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

        base_label = tank_data.get("label", f"Tank {tank_id + 1}")
        self._attr_unique_id = f"{entry.entry_id}_tank_{tank_id}_full"
        self._attr_name = f"{base_label} Full"

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
        tank = tanks.get(self._tank_id)
        if tank:
            nivel = tank.get("nivel", 0xFF)
            return nivel != 0xFF and nivel not in (2, 3) and super().available
        return False

    @property
    def is_on(self) -> bool:
        """Return true if the tank is full."""
        tanks = self.coordinator.get_tanks()
        tank = tanks.get(self._tank_id)
        if tank:
            return tank.get("nivel", 0xFF) == TANK_FULL
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
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
            return {
                "level_raw": nivel,
                "level": level_map.get(nivel, "unknown"),
            }
        return {}


class HidromoticTankEmptySensor(
    CoordinatorEntity[HidromoticCoordinator], BinarySensorEntity
):
    """Binary sensor for tank empty status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

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

        base_label = tank_data.get("label", f"Tank {tank_id + 1}")
        self._attr_unique_id = f"{entry.entry_id}_tank_{tank_id}_empty"
        self._attr_name = f"{base_label} Empty"

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
        tank = tanks.get(self._tank_id)
        if tank:
            nivel = tank.get("nivel", 0xFF)
            return nivel != 0xFF and nivel not in (2, 3) and super().available
        return False

    @property
    def is_on(self) -> bool:
        """Return true if the tank is empty (problem state)."""
        tanks = self.coordinator.get_tanks()
        tank = tanks.get(self._tank_id)
        if tank:
            return tank.get("nivel", 0xFF) == TANK_EMPTY
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
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
            return {
                "level_raw": nivel,
                "level": level_map.get(nivel, "unknown"),
            }
        return {}
