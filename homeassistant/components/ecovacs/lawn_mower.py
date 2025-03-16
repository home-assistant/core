"""Ecovacs mower entity."""

from __future__ import annotations

import logging

from deebot_client.capabilities import Capabilities, DeviceType
from deebot_client.device import Device
from deebot_client.events import StateEvent
from deebot_client.models import CleanAction, State

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityEntityDescription,
    LawnMowerEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcovacsConfigEntry
from .entity import EcovacsEntity

_LOGGER = logging.getLogger(__name__)


_STATE_TO_MOWER_STATE = {
    State.IDLE: LawnMowerActivity.PAUSED,
    State.CLEANING: LawnMowerActivity.MOWING,
    State.RETURNING: LawnMowerActivity.RETURNING,
    State.DOCKED: LawnMowerActivity.DOCKED,
    State.ERROR: LawnMowerActivity.ERROR,
    State.PAUSED: LawnMowerActivity.PAUSED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ecovacs mowers."""
    controller = config_entry.runtime_data
    mowers: list[EcovacsMower] = [
        EcovacsMower(device)
        for device in controller.devices
        if device.capabilities.device_type is DeviceType.MOWER
    ]
    _LOGGER.debug("Adding Ecovacs Mowers to Home Assistant: %s", mowers)
    async_add_entities(mowers)


class EcovacsMower(
    EcovacsEntity[Capabilities],
    LawnMowerEntity,
):
    """Ecovacs Mower."""

    _attr_supported_features = (
        LawnMowerEntityFeature.DOCK
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.START_MOWING
    )

    entity_description = LawnMowerEntityEntityDescription(key="mower", name=None)

    def __init__(self, device: Device) -> None:
        """Initialize the mower."""
        super().__init__(device, device.capabilities)

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_status(event: StateEvent) -> None:
            self._attr_activity = _STATE_TO_MOWER_STATE[event.state]
            self.async_write_ha_state()

        self._subscribe(self._capability.state.event, on_status)

    async def _clean_command(self, action: CleanAction) -> None:
        await self._device.execute_command(
            self._capability.clean.action.command(action)
        )

    async def async_start_mowing(self) -> None:
        """Resume schedule."""
        await self._clean_command(CleanAction.START)

    async def async_pause(self) -> None:
        """Pauses the mower."""
        await self._clean_command(CleanAction.PAUSE)

    async def async_dock(self) -> None:
        """Parks the mower until next schedule."""
        await self._device.execute_command(self._capability.charge.execute())
