"""Support for the Vallox ventilation unit fan."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, NamedTuple

from vallox_websocket_api import Vallox
from vallox_websocket_api.exceptions import ValloxApiException

from homeassistant.components.fan import (
    SUPPORT_PRESET_MODE,
    FanEntity,
    NotValidPresetModeError,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ValloxDataUpdateCoordinator
from .const import (
    DOMAIN,
    METRIC_KEY_MODE,
    METRIC_KEY_PROFILE_FAN_SPEED_AWAY,
    METRIC_KEY_PROFILE_FAN_SPEED_BOOST,
    METRIC_KEY_PROFILE_FAN_SPEED_HOME,
    MODE_OFF,
    MODE_ON,
    STR_TO_VALLOX_PROFILE_SETTABLE,
    VALLOX_PROFILE_TO_STR_SETTABLE,
)

_LOGGER = logging.getLogger(__name__)


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


def _convert_fan_speed_value(value: StateType) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)

    return None


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the fan device."""
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]["client"]
    client.set_settable_address(METRIC_KEY_MODE, int)

    device = ValloxFan(
        hass.data[DOMAIN]["name"], client, hass.data[DOMAIN]["coordinator"]
    )

    async_add_entities([device])


class ValloxFan(CoordinatorEntity, FanEntity):
    """Representation of the fan."""

    coordinator: ValloxDataUpdateCoordinator

    def __init__(
        self,
        name: str,
        client: Vallox,
        coordinator: ValloxDataUpdateCoordinator,
    ) -> None:
        """Initialize the fan."""
        super().__init__(coordinator)

        self._client = client

        self._attr_name = name

        self._attr_unique_id = str(self.coordinator.data.get_uuid())

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_PRESET_MODE

    @property
    def preset_modes(self) -> list[str]:
        """Return a list of available preset modes."""
        # Use the Vallox profile names for the preset names.
        return list(STR_TO_VALLOX_PROFILE_SETTABLE.keys())

    @property
    def is_on(self) -> bool:
        """Return if device is on."""
        return self.coordinator.data.get_metric(METRIC_KEY_MODE) == MODE_ON

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        vallox_profile = self.coordinator.data.profile
        return VALLOX_PROFILE_TO_STR_SETTABLE.get(vallox_profile)

    @property
    def extra_state_attributes(self) -> Mapping[str, int | None]:
        """Return device specific state attributes."""
        data = self.coordinator.data

        return {
            attr.description: _convert_fan_speed_value(data.get_metric(attr.metric_key))
            for attr in EXTRA_STATE_ATTRIBUTES
        }

    async def _async_set_preset_mode_internal(self, preset_mode: str) -> bool:
        """
        Set new preset mode.

        Returns true if the mode has been changed, false otherwise.
        """
        try:
            self._valid_preset_mode_or_raise(preset_mode)  # type: ignore[no-untyped-call]

        except NotValidPresetModeError as err:
            _LOGGER.error(err)
            return False

        if preset_mode == self.preset_mode:
            return False

        try:
            await self._client.set_profile(STR_TO_VALLOX_PROFILE_SETTABLE[preset_mode])

        except (OSError, ValloxApiException) as err:
            _LOGGER.error("Error setting preset: %s", err)
            return False

        return True

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        update_needed = await self._async_set_preset_mode_internal(preset_mode)

        if update_needed:
            # This state change affects other entities like sensors. Force an immediate update that
            # can be observed by all parties involved.
            await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        _LOGGER.debug("Turn on")

        update_needed = False

        if preset_mode:
            update_needed = await self._async_set_preset_mode_internal(preset_mode)

        if not self.is_on:
            try:
                await self._client.set_values({METRIC_KEY_MODE: MODE_ON})

            except OSError as err:
                _LOGGER.error("Error turning on: %s", err)

            else:
                update_needed = True

        if update_needed:
            # This state change affects other entities like sensors. Force an immediate update that
            # can be observed by all parties involved.
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if not self.is_on:
            return

        try:
            await self._client.set_values({METRIC_KEY_MODE: MODE_OFF})

        except OSError as err:
            _LOGGER.error("Error turning off: %s", err)
            return

        # Same as for turn_on method.
        await self.coordinator.async_request_refresh()
