"""Vacuum platform for SmartThings integration."""

from __future__ import annotations

import logging
from typing import Any

from pysmartthings import Command
from pysmartthings.capability import Capability

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity

_LOGGER = logging.getLogger(__name__)


SUPPORTED_FEATURES = (
    VacuumEntityFeature.TURN_ON
    | VacuumEntityFeature.TURN_OFF
    | VacuumEntityFeature.START
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.STATE
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Jet Bot vacuum entity from SmartThings entry."""
    entry_data = entry.runtime_data
    vacuums = [
        SamsungJetBotVacuum(entry_data.client, device)
        for device in entry_data.devices.values()
        if isinstance(device.status.get(MAIN), dict)
        and "samsungce.robotCleanerOperatingState" in device.status[MAIN]
    ]
    async_add_entities(vacuums)


class SamsungJetBotVacuum(SmartThingsEntity, StateVacuumEntity):
    """Minimal Samsung Jet Bot vacuum entity."""

    def __init__(self, client, device: FullDevice) -> None:
        """Initialize Jet Bot vacuum."""
        super().__init__(client, device, set())
        self._attr_name = "Samsung Jet Bot"
        self._attr_unique_id = f"{device.device.device_id}_vacuum"
        self._attr_supported_features = SUPPORTED_FEATURES

    @property
    def activity(self) -> VacuumActivity:
        """Return the current vacuum activity using VacuumActivity enum."""
        op_state = (
            self.device.status[MAIN]
            .get("samsungce.robotCleanerOperatingState", {})
            .get("operatingState")
        )

        if isinstance(op_state, dict):
            op_state = op_state.get("value")

        if not isinstance(op_state, str):
            return VacuumActivity.IDLE

        raw = op_state.lower()

        if raw == "cleaning":
            return VacuumActivity.CLEANING
        if raw in ("returning", "returntohome", "return_to_base"):
            return VacuumActivity.RETURNING
        if raw == "idle":
            return VacuumActivity.IDLE
        if raw == "paused":
            return VacuumActivity.PAUSED
        if raw == "docked":
            return VacuumActivity.DOCKED

        return VacuumActivity.IDLE

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send start command via turn_on."""
        await self.execute_device_command(
            Capability("samsungce.robotCleanerOperatingState"),
            Command("start"),
        )

    async def async_start(self) -> None:
        """Send start command via start."""
        await self.execute_device_command(
            Capability("samsungce.robotCleanerOperatingState"),
            Command("start"),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send returnToHome command via turn_off."""
        await self.execute_device_command(
            Capability("samsungce.robotCleanerOperatingState"),
            Command("returnToHome"),
        )

    async def async_pause(self) -> None:
        """Send pause command."""
        await self.execute_device_command(
            Capability("samsungce.robotCleanerOperatingState"),
            Command("pause"),
        )

    async def async_stop(self, **kwargs: Any) -> None:
        """Send returnToHome command via stop."""
        await self.execute_device_command(
            Capability("samsungce.robotCleanerOperatingState"),
            Command("returnToHome"),
        )
