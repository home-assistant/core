"""SmartThings vacuum platform."""

from __future__ import annotations

import logging
from typing import Any

from pysmartthings import Attribute, Command, SmartThings
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up vacuum entities from SmartThings devices."""
    entry_data = entry.runtime_data
    async_add_entities(
        SamsungJetBotVacuum(entry_data.client, device)
        for device in entry_data.devices.values()
        if Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE in device.status[MAIN]
    )


class SamsungJetBotVacuum(SmartThingsEntity, StateVacuumEntity):
    """Representation of a Vacuum."""

    _attr_name = None
    _attr_supported_features = (
        VacuumEntityFeature.START
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STATE
    )

    def __init__(self, client: SmartThings, device: FullDevice) -> None:
        """Initialize the Samsung robot cleaner vacuum entity."""
        super().__init__(
            client,
            device,
            {Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE},
        )

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the current vacuum activity based on operating state."""
        status = self.get_attribute_value(
            Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE,
            Attribute.OPERATING_STATE,
        )

        return {
            "cleaning": VacuumActivity.CLEANING,
            "homing": VacuumActivity.RETURNING,
            "idle": VacuumActivity.IDLE,
            "paused": VacuumActivity.PAUSED,
            "docked": VacuumActivity.DOCKED,
            "error": VacuumActivity.ERROR,
            "charging": VacuumActivity.DOCKED,
        }.get(status)

    async def async_start(self) -> None:
        """Start the vacuum's operation."""
        await self.execute_device_command(
            Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE,
            Command.START,
        )

    async def async_pause(self) -> None:
        """Pause the vacuum's current operation."""
        await self.execute_device_command(
            Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE, Command.PAUSE
        )

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return the vacuum to its base."""
        await self.execute_device_command(
            Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE,
            Command.RETURN_TO_HOME,
        )
