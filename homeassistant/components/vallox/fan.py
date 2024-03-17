"""Support for the Vallox ventilation unit fan."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NamedTuple

from vallox_websocket_api import Vallox, ValloxApiException, ValloxInvalidInputException

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import ValloxDataUpdateCoordinator, ValloxEntity
from .const import (
    DOMAIN,
    METRIC_KEY_MODE,
    METRIC_KEY_PROFILE_FAN_SPEED_AWAY,
    METRIC_KEY_PROFILE_FAN_SPEED_BOOST,
    METRIC_KEY_PROFILE_FAN_SPEED_HOME,
    MODE_OFF,
    MODE_ON,
    PRESET_MODE_TO_VALLOX_PROFILE_SETTABLE,
    VALLOX_PROFILE_TO_PRESET_MODE_REPORTABLE,
)


class ExtraStateAttributeDetails(NamedTuple):
    """Extra state attribute details."""

    description: str
    metric_key: str


EXTRA_STATE_ATTRIBUTES = (
    ExtraStateAttributeDetails(
        description="fan_speed_home", metric_key=METRIC_KEY_PROFILE_FAN_SPEED_HOME
    ),
    ExtraStateAttributeDetails(
        description="fan_speed_away", metric_key=METRIC_KEY_PROFILE_FAN_SPEED_AWAY
    ),
    ExtraStateAttributeDetails(
        description="fan_speed_boost", metric_key=METRIC_KEY_PROFILE_FAN_SPEED_BOOST
    ),
)


def _convert_to_int(value: StateType) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)

    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the fan device."""
    data = hass.data[DOMAIN][entry.entry_id]

    client = data["client"]

    device = ValloxFanEntity(
        data["name"],
        client,
        data["coordinator"],
    )

    async_add_entities([device])


class ValloxFanEntity(ValloxEntity, FanEntity):
    """Representation of the fan."""

    _attr_name = None
    _attr_supported_features = FanEntityFeature.PRESET_MODE | FanEntityFeature.SET_SPEED

    def __init__(
        self,
        name: str,
        client: Vallox,
        coordinator: ValloxDataUpdateCoordinator,
    ) -> None:
        """Initialize the fan."""
        super().__init__(name, coordinator)

        self._client = client

        self._attr_unique_id = str(self._device_uuid)
        self._attr_preset_modes = list(PRESET_MODE_TO_VALLOX_PROFILE_SETTABLE)

    @property
    def is_on(self) -> bool:
        """Return if device is on."""
        return self.coordinator.data.get(METRIC_KEY_MODE) == MODE_ON

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        vallox_profile = self.coordinator.data.profile
        return VALLOX_PROFILE_TO_PRESET_MODE_REPORTABLE.get(vallox_profile)

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""

        vallox_profile = self.coordinator.data.profile
        try:
            return _convert_to_int(self.coordinator.data.get_fan_speed(vallox_profile))
        except ValloxInvalidInputException:
            return None

    @property
    def extra_state_attributes(self) -> Mapping[str, int | None]:
        """Return device specific state attributes."""
        data = self.coordinator.data

        return {
            attr.description: _convert_to_int(data.get(attr.metric_key))
            for attr in EXTRA_STATE_ATTRIBUTES
        }

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        update_needed = await self._async_set_preset_mode_internal(preset_mode)

        if update_needed:
            # This state change affects other entities like sensors. Force an immediate update that
            # can be observed by all parties involved.
            await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        update_needed = False

        if not self.is_on:
            update_needed |= await self._async_set_power(True)

        if preset_mode:
            update_needed |= await self._async_set_preset_mode_internal(preset_mode)

        if percentage is not None:
            update_needed |= await self._async_set_percentage_internal(
                percentage, preset_mode
            )

        if update_needed:
            # This state change affects other entities like sensors. Force an immediate update that
            # can be observed by all parties involved.
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if not self.is_on:
            return

        update_needed = await self._async_set_power(False)

        if update_needed:
            await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return

        update_needed = await self._async_set_percentage_internal(percentage)

        if update_needed:
            await self.coordinator.async_request_refresh()

    async def _async_set_power(self, mode: bool) -> bool:
        try:
            await self._client.set_values(
                {METRIC_KEY_MODE: MODE_ON if mode else MODE_OFF}
            )
        except ValloxApiException as err:
            raise HomeAssistantError("Failed to set power mode") from err

        return True

    async def _async_set_preset_mode_internal(self, preset_mode: str) -> bool:
        """Set new preset mode.

        Returns true if the mode has been changed, false otherwise.
        """
        if preset_mode == self.preset_mode:
            return False

        try:
            profile = PRESET_MODE_TO_VALLOX_PROFILE_SETTABLE[preset_mode]
            await self._client.set_profile(profile)

        except ValloxApiException as err:
            raise HomeAssistantError(f"Failed to set profile: {preset_mode}") from err

        return True

    async def _async_set_percentage_internal(
        self, percentage: int, preset_mode: str | None = None
    ) -> bool:
        """Set fan speed percentage for current profile.

        Returns true if speed has been changed, false otherwise.
        """
        vallox_profile = (
            PRESET_MODE_TO_VALLOX_PROFILE_SETTABLE[preset_mode]
            if preset_mode is not None
            else self.coordinator.data.profile
        )

        try:
            await self._client.set_fan_speed(vallox_profile, percentage)
        except ValloxInvalidInputException as err:
            # This can happen if current profile does not support setting the fan speed.
            raise ValueError(
                f"{vallox_profile} profile does not support setting the fan speed"
            ) from err
        except ValloxApiException as err:
            raise HomeAssistantError("Failed to set fan speed") from err

        return True
