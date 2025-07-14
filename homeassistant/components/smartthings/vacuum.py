"""VacuumJet Bot."""

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

# ───────────────────────────────────────────────
# Supported Vacuum Features
# ───────────────────────────────────────────────
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
    """Set up Samsung Jet Bot vacuum entities from SmartThings devices."""
    entry_data = entry.runtime_data
    async_add_entities(
        SamsungJetBotVacuum(entry_data.client, device)
        for device in entry_data.devices.values()
        if isinstance(device.status.get(MAIN), dict)
        and Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE in device.status[MAIN]
    )


class SamsungJetBotVacuum(SmartThingsEntity, StateVacuumEntity):
    """Representation of a Samsung Jet Bot vacuum as a Home Assistant entity."""

    def __init__(self, client, device: FullDevice) -> None:
        """Initialize the Jet Bot vacuum entity."""
        super().__init__(
            client,
            device,
            {
                Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE,
                Capability.SAMSUNG_CE_ROBOT_CLEANER_CLEANING_TYPE,
                Capability.SAMSUNG_CE_ROBOT_CLEANER_DRIVING_MODE,
                Capability.SAMSUNG_CE_ROBOT_CLEANER_WATER_SPRAY_LEVEL,
            },
        )
        self._attr_unique_id = f"{device.device.device_id}"
        self._attr_supported_features = SUPPORTED_FEATURES

    @property
    def activity(self) -> VacuumActivity:
        """Return the current vacuum activity based on operating state."""
        op_state = (
            self.device.status[MAIN]
            .get(Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE, {})
            .get("operatingState")
        )

        self._attr_name = None

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

    # ───────────────────────────────────────────────
    # Logging
    # ───────────────────────────────────────────────
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send `start` command to begin cleaning."""
        _LOGGER.debug("Jet Bot: Sending 'start' via turn_on")
        await self.execute_device_command(
            Capability(Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE),
            Command.START,
        )

    async def async_start(self) -> None:
        """Send `start` command to begin cleaning."""
        _LOGGER.debug("Jet Bot: Sending 'start' via start")
        await self.execute_device_command(
            Capability(Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE),
            Command("start"),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send `returnToHome` command to dock the vacuum."""
        _LOGGER.debug("Jet Bot: Sending 'returnToHome' via turn_off")
        await self.execute_device_command(
            Capability(Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE),
            Command("returnToHome"),
        )

    async def async_pause(self) -> None:
        """Send `pause` command to pause cleaning."""
        _LOGGER.debug("Jet Bot: Sending 'pause'")
        await self.execute_device_command(
            Capability(Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE),
            Command("pause"),
        )

    async def async_stop(self, **kwargs: Any) -> None:
        """Send `returnToHome` command to stop and return to dock."""
        _LOGGER.debug("Jet Bot: Sending 'returnToHome' via stop")
        await self.execute_device_command(
            Capability(Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE),
            Command("returnToHome"),
        )
