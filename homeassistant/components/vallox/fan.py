"""Support for the Vallox ventilation unit fan."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from vallox_websocket_api import Vallox
from vallox_websocket_api.exceptions import ValloxApiException

from homeassistant.components.fan import (
    SUPPORT_PRESET_MODE,
    FanEntity,
    NotValidPresetModeError,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import ValloxStateProxy
from .const import (
    DOMAIN,
    METRIC_KEY_MODE,
    METRIC_KEY_PROFILE_FAN_SPEED_AWAY,
    METRIC_KEY_PROFILE_FAN_SPEED_BOOST,
    METRIC_KEY_PROFILE_FAN_SPEED_HOME,
    MODE_OFF,
    MODE_ON,
    SIGNAL_VALLOX_STATE_UPDATE,
    STR_TO_VALLOX_PROFILE_SETTABLE,
    VALLOX_PROFILE_TO_STR_SETTABLE,
)

_LOGGER = logging.getLogger(__name__)

ATTR_PROFILE_FAN_SPEED_HOME = {
    "description": "fan_speed_home",
    "metric_key": METRIC_KEY_PROFILE_FAN_SPEED_HOME,
}
ATTR_PROFILE_FAN_SPEED_AWAY = {
    "description": "fan_speed_away",
    "metric_key": METRIC_KEY_PROFILE_FAN_SPEED_AWAY,
}
ATTR_PROFILE_FAN_SPEED_BOOST = {
    "description": "fan_speed_boost",
    "metric_key": METRIC_KEY_PROFILE_FAN_SPEED_BOOST,
}


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
        hass.data[DOMAIN]["name"], client, hass.data[DOMAIN]["state_proxy"]
    )

    async_add_entities([device], update_before_add=False)


class ValloxFan(FanEntity):
    """Representation of the fan."""

    _attr_should_poll = False

    def __init__(
        self, name: str, client: Vallox, state_proxy: ValloxStateProxy
    ) -> None:
        """Initialize the fan."""
        self._client = client
        self._state_proxy = state_proxy
        self._is_on = False
        self._preset_mode: str | None = None
        self._fan_speed_home: int | None = None
        self._fan_speed_away: int | None = None
        self._fan_speed_boost: int | None = None

        self._attr_name = name
        self._attr_available = False

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
        return self._is_on

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._preset_mode

    @property
    def extra_state_attributes(self) -> Mapping[str, int | None]:
        """Return device specific state attributes."""
        return {
            ATTR_PROFILE_FAN_SPEED_HOME["description"]: self._fan_speed_home,
            ATTR_PROFILE_FAN_SPEED_AWAY["description"]: self._fan_speed_away,
            ATTR_PROFILE_FAN_SPEED_BOOST["description"]: self._fan_speed_boost,
        }

    async def async_added_to_hass(self) -> None:
        """Call to update."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_VALLOX_STATE_UPDATE, self._update_callback
            )
        )

    @callback
    def _update_callback(self) -> None:
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Fetch state from the device."""
        try:
            # Fetch if the whole device is in regular operation state.
            self._is_on = self._state_proxy.fetch_metric(METRIC_KEY_MODE) == MODE_ON

            vallox_profile = self._state_proxy.get_profile()

            # Fetch the profile fan speeds.
            fan_speed_home = self._state_proxy.fetch_metric(
                ATTR_PROFILE_FAN_SPEED_HOME["metric_key"]
            )
            fan_speed_away = self._state_proxy.fetch_metric(
                ATTR_PROFILE_FAN_SPEED_AWAY["metric_key"]
            )
            fan_speed_boost = self._state_proxy.fetch_metric(
                ATTR_PROFILE_FAN_SPEED_BOOST["metric_key"]
            )

        except (OSError, KeyError, TypeError) as err:
            self._attr_available = False
            _LOGGER.error("Error updating fan: %s", err)
            return

        self._preset_mode = VALLOX_PROFILE_TO_STR_SETTABLE.get(vallox_profile)

        self._fan_speed_home = (
            int(fan_speed_home) if isinstance(fan_speed_home, (int, float)) else None
        )
        self._fan_speed_away = (
            int(fan_speed_away) if isinstance(fan_speed_away, (int, float)) else None
        )
        self._fan_speed_boost = (
            int(fan_speed_boost) if isinstance(fan_speed_boost, (int, float)) else None
        )

        self._attr_available = True

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
            await self._state_proxy.async_update()

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        _LOGGER.debug("Turn on: %s", speed)

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
            await self._state_proxy.async_update()

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
        await self._state_proxy.async_update()
