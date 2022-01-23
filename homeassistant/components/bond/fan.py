"""Support for Bond fans."""
from __future__ import annotations

import logging
import math
from typing import Any

from aiohttp.client_exceptions import ClientResponseError
from bond_api import Action, BPUPSubscriptions, DeviceType, Direction
import voluptuous as vol

from homeassistant.components.fan import (
    ATTR_SPEED,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    SUPPORT_DIRECTION,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import BPUP_SUBS, DOMAIN, HUB, SERVICE_SET_FAN_SPEED_TRACKED_STATE
from .entity import BondEntity
from .utils import BondDevice, BondHub

_LOGGER = logging.getLogger(__name__)

PRESET_MODE_BREEZE = "Breeze"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond fan devices."""
    data = hass.data[DOMAIN][entry.entry_id]
    hub: BondHub = data[HUB]
    bpup_subs: BPUPSubscriptions = data[BPUP_SUBS]
    platform = entity_platform.async_get_current_platform()

    fans: list[Entity] = [
        BondFan(hub, device, bpup_subs)
        for device in hub.devices
        if DeviceType.is_fan(device.type)
    ]

    platform.async_register_entity_service(
        SERVICE_SET_FAN_SPEED_TRACKED_STATE,
        {vol.Required(ATTR_SPEED): vol.All(vol.Number(scale=0), vol.Range(0, 100))},
        "async_set_speed_belief",
    )

    async_add_entities(fans, True)


class BondFan(BondEntity, FanEntity):
    """Representation of a Bond fan."""

    def __init__(
        self, hub: BondHub, device: BondDevice, bpup_subs: BPUPSubscriptions
    ) -> None:
        """Create HA entity representing Bond fan."""
        super().__init__(hub, device, bpup_subs)

        self._power: bool | None = None
        self._speed: int | None = None
        self._direction: int | None = None
        if self._device.has_action(Action.BREEZE_ON):
            self._attr_preset_modes = [PRESET_MODE_BREEZE]

    def _apply_state(self, state: dict) -> None:
        _LOGGER.critical("preset mode: %s", state)

        self._power = state.get("power")
        self._speed = state.get("speed")
        self._direction = state.get("direction")

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        features = 0
        if self._device.supports_speed():
            features |= SUPPORT_SET_SPEED
        if self._device.supports_direction():
            features |= SUPPORT_DIRECTION

        return features

    @property
    def _speed_range(self) -> tuple[int, int]:
        """Return the range of speeds."""
        return (1, self._device.props.get("max_speed", 3))

    @property
    def percentage(self) -> int:
        """Return the current speed percentage for the fan."""
        if not self._speed or not self._power:
            return 0
        return ranged_value_to_percentage(self._speed_range, self._speed)

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

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset_mode."""
        _LOGGER.critical("preset mode: %s", self._device.props.get("breeze"))
        return PRESET_MODE_BREEZE if self._device.props.get("breeze") else None

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
                f"The bond API returned an error calling set_power_state_belief for {self.entity_id}.  Code: {ex.code}  Message: {ex.message}"
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
                f"The bond API returned an error calling set_speed_belief for {self.entity_id}.  Code: {ex.code}  Message: {ex.message}"
            ) from ex

    async def async_turn_on(
        self,
        speed: str | None = None,
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
        if preset_mode != PRESET_MODE_BREEZE:
            raise ValueError(f"Invalid preset mode: {preset_mode}")
        await self._hub.bond.action(self._device.device_id, Action(Action.BREEZE_ON))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._hub.bond.action(self._device.device_id, Action.turn_off())

    async def async_set_direction(self, direction: str) -> None:
        """Set fan rotation direction."""
        bond_direction = (
            Direction.REVERSE if direction == DIRECTION_REVERSE else Direction.FORWARD
        )
        await self._hub.bond.action(
            self._device.device_id, Action.set_direction(bond_direction)
        )
