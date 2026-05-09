"""Ecovacs mower entity."""

import logging
from typing import Any

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
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcovacsConfigEntry
from .const import DOMAIN
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

    async def async_raw_get_positions(
        self,
    ) -> dict[str, Any]:
        """Get the raw positions response for the mower and its charging dock.

        Mirrors the modern vacuum implementation so service
        `ecovacs.raw_get_positions` works on `lawn_mower.*` ecovacs entities.
        Useful for inspecting additional payload fields the cloud may return
        for RTK GOAT mowers (e.g. satellite counts, fix quality, signal
        strength), which can then be parsed and exposed by deebot-client and
        this integration in follow-up changes.
        """
        _LOGGER.debug("async_raw_get_positions")

        if not (map_cap := self._capability.map) or not (
            position_commands := map_cap.position.get
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="raw_get_positions_not_supported",
            )

        return await self._device.execute_command(position_commands[0])
