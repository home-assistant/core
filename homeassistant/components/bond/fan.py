"""Support for Bond fans."""

from __future__ import annotations

import logging
import math
from typing import Any

from aiohttp.client_exceptions import ClientResponseError
from bond_async import Action, BPUPSubscriptions, DeviceType, Direction
import voluptuous as vol

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from . import BondConfigEntry
from .const import SERVICE_SET_FAN_SPEED_TRACKED_STATE
from .entity import BondEntity
from .utils import BondDevice, BondHub

_LOGGER = logging.getLogger(__name__)

PRESET_MODE_BREEZE = "Breeze"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BondConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond fan devices."""
    data = entry.runtime_data
    hub = data.hub
    bpup_subs = data.bpup_subs
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_FAN_SPEED_TRACKED_STATE,
        {vol.Required("speed"): vol.All(vol.Number(scale=0), vol.Range(0, 100))},
        "async_set_speed_belief",
    )

    async_add_entities(
        BondFan(hub, device, bpup_subs)
        for device in hub.devices
        if DeviceType.is_fan(device.type)
    )


class BondFan(BondEntity, FanEntity):
    """Representation of a Bond fan."""

    def __init__(
        self, hub: BondHub, device: BondDevice, bpup_subs: BPUPSubscriptions
    ) -> None:
        """Create HA entity representing Bond fan."""
        self._power: bool | None = None
        self._speed: int | None = None
        self._direction: int | None = None
        super().__init__(hub, device, bpup_subs)
        if self._device.has_action(Action.BREEZE_ON):
            self._attr_preset_modes = [PRESET_MODE_BREEZE]
        features = FanEntityFeature(0)
        if self._device.supports_speed():
            features |= FanEntityFeature.SET_SPEED
        if self._device.supports_direction():
            features |= FanEntityFeature.DIRECTION
        if self._device.has_action(Action.BREEZE_ON):
            features |= FanEntityFeature.PRESET_MODE
        self._attr_supported_features = features

    def _apply_state(self) -> None:
        state = self._device.state
        self._power = state.get("power")
        self._speed = state.get("speed")
        self._direction = state.get("direction")
        breeze = state.get("breeze", [0, 0, 0])
        self._attr_preset_mode = PRESET_MODE_BREEZE if breeze[0] else None

    @property
    def _speed_range(self) -> tuple[int, int]:
        """Return the range of speeds."""
        return (1, self._device.props.get("max_speed", 3))

    @property
    def percentage(self) -> int:
        """Return the current speed percentage for the fan."""
        if not self._speed or not self._power:
            return 0
        return min(
            100, max(0, ranged_value_to_percentage(self._speed_range, self._speed))
        )

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(self._speed_range)

    @property
    def current_direction(self) -> str | None:
        """Return fan rotation direction."""
        direction = None
        if self._direction == Direction.FORWARD:
            direction = DIRECTION_FORWARD
        elif self._direction == Direction.REVERSE:
            direction = DIRECTION_REVERSE

        return direction

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the desired speed for the fan."""
        _LOGGER.debug("async_set_percentage called with percentage %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        bond_speed = math.ceil(
            percentage_to_ranged_value(self._speed_range, percentage)
        )
        _LOGGER.debug(
            "async_set_percentage converted percentage %s to bond speed %s",
            percentage,
            bond_speed,
        )

        await self._hub.bond.action(
            self._device.device_id, Action.set_speed(bond_speed)
        )

    async def async_set_power_belief(self, power_state: bool) -> None:
        """Set the believed state to on or off."""
        try:
            await self._hub.bond.action(
                self._device.device_id, Action.set_power_state_belief(power_state)
            )
        except ClientResponseError as ex:
            raise HomeAssistantError(
                "The bond API returned an error calling set_power_state_belief for"
                f" {self.entity_id}.  Code: {ex.status}  Message: {ex.message}"
            ) from ex

    async def async_set_speed_belief(self, speed: int) -> None:
        """Set the believed speed for the fan."""
        _LOGGER.debug("async_set_speed_belief called with percentage %s", speed)
        if speed == 0:
            await self.async_set_power_belief(False)
            return

        await self.async_set_power_belief(True)

        bond_speed = math.ceil(percentage_to_ranged_value(self._speed_range, speed))
        _LOGGER.debug(
            "async_set_percentage converted percentage %s to bond speed %s",
            speed,
            bond_speed,
        )
        try:
            await self._hub.bond.action(
                self._device.device_id, Action.set_speed_belief(bond_speed)
            )
        except ClientResponseError as ex:
            raise HomeAssistantError(
                "The bond API returned an error calling set_speed_belief for"
                f" {self.entity_id}.  Code: {ex.code}  Message: {ex.message}"
            ) from ex

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        _LOGGER.debug("Fan async_turn_on called with percentage %s", percentage)

        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self._hub.bond.action(self._device.device_id, Action.turn_on())

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        await self._hub.bond.action(self._device.device_id, Action(Action.BREEZE_ON))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        if self.preset_mode == PRESET_MODE_BREEZE:
            await self._hub.bond.action(
                self._device.device_id, Action(Action.BREEZE_OFF)
            )
        await self._hub.bond.action(self._device.device_id, Action.turn_off())

    async def async_set_direction(self, direction: str) -> None:
        """Set fan rotation direction."""
        bond_direction = (
            Direction.REVERSE if direction == DIRECTION_REVERSE else Direction.FORWARD
        )
        await self._hub.bond.action(
            self._device.device_id, Action.set_direction(bond_direction)
        )
