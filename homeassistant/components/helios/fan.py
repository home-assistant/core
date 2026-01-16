"""Support for the Helios ventilation unit fan."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, time
from typing import Any, NamedTuple

from helios_websocket_api import Helios, HeliosApiException, HeliosInvalidInputException

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    HELIOS_CELL_STATE_TO_STR,
    HELIOS_PROFILE_TO_PRESET_MODE,
    METRIC_KEY_MODE,
    METRIC_KEY_PROFILE_FAN_SPEED_AWAY,
    METRIC_KEY_PROFILE_FAN_SPEED_BOOST,
    METRIC_KEY_PROFILE_FAN_SPEED_HOME,
    MODE_OFF,
    MODE_ON,
    PRESET_MODE_TO_HELIOS_PROFILE,
)
from .coordinator import HeliosDataUpdateCoordinator
from .entity import HeliosEntity


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
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the fan device."""
    data = hass.data[DOMAIN][entry.entry_id]

    client = data["client"]

    device = HeliosFanEntity(
        data["name"],
        client,
        data["coordinator"],
    )

    async_add_entities([device])


class HeliosFanEntity(HeliosEntity, FanEntity):
    """Representation of the fan."""

    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )

    def __init__(
        self,
        name: str,
        client: Helios,
        coordinator: HeliosDataUpdateCoordinator,
    ) -> None:
        """Initialize the fan."""
        super().__init__(name, coordinator)

        self._client = client

        self._attr_unique_id = str(self._device_uuid)
        self._attr_preset_modes = list(PRESET_MODE_TO_HELIOS_PROFILE)

    @property
    def is_on(self) -> bool:
        """Return if device is on."""
        return self.coordinator.data.get(METRIC_KEY_MODE) == MODE_ON

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        helios_profile = self.coordinator.data.profile
        return HELIOS_PROFILE_TO_PRESET_MODE.get(helios_profile)

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""

        helios_profile = self.coordinator.data.profile
        try:
            return _convert_to_int(self.coordinator.data.get_fan_speed(helios_profile))
        except HeliosInvalidInputException:
            return None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return device specific state attributes."""
        data = self.coordinator.data
        helios_profile = data.profile
        fan_is_on = data.get(METRIC_KEY_MODE) == MODE_ON

        # Get filter change date and calculate remaining time
        next_filter_change_date = data.next_filter_change_date
        filter_remaining_time = None
        if next_filter_change_date is not None:
            filter_remaining_time = datetime.combine(
                next_filter_change_date,
                time(hour=13, minute=0, second=0, tzinfo=dt_util.get_default_time_zone()),
            )

        # Get cell state
        cell_state_value = data.get("A_CYC_CELL_STATE")
        cell_state = (
            HELIOS_CELL_STATE_TO_STR.get(cell_state_value)
            if isinstance(cell_state_value, int)
            else None
        )

        # Get efficiency
        efficiency_value = data.get("A_CYC_EXTRACT_EFFICIENCY")
        efficiency = (
            round(efficiency_value, 0) if isinstance(efficiency_value, float) else efficiency_value
        )

        attributes = {
            # Profile fan speeds
            attr.description: _convert_to_int(data.get(attr.metric_key))
            for attr in EXTRA_STATE_ATTRIBUTES
        }

        # Add all sensor data as attributes
        attributes.update({
            # Profile information
            "current_profile": HELIOS_PROFILE_TO_PRESET_MODE.get(helios_profile),
            "profile_duration": data.get_remaining_profile_duration(helios_profile),
            # Fan speeds
            "fan_speed": _convert_to_int(data.get("A_CYC_FAN_SPEED")) if fan_is_on else 0,
            "extract_fan_speed": _convert_to_int(data.get("A_CYC_EXTR_FAN_SPEED")) if fan_is_on else 0,
            "supply_fan_speed": _convert_to_int(data.get("A_CYC_SUPP_FAN_SPEED")) if fan_is_on else 0,
            # Filter information
            "remaining_time_for_filter": filter_remaining_time,
            "filter_change_date": data.filter_change_date,
            # Cell state
            "cell_state": cell_state,
            # Temperature sensors
            "extract_air_temp": data.get("A_CYC_TEMP_EXTRACT_AIR"),
            "exhaust_air_temp": data.get("A_CYC_TEMP_EXHAUST_AIR"),
            "outdoor_air_temp": data.get("A_CYC_TEMP_OUTDOOR_AIR"),
            "supply_air_temp": data.get("A_CYC_TEMP_SUPPLY_AIR"),
            "supply_cell_air_temp": data.get("A_CYC_TEMP_SUPPLY_CELL_AIR"),
            "optional_air_temp": data.get("A_CYC_TEMP_OPTIONAL"),
            # Target temperatures (from number entities)
            "supply_air_target_home": data.get("A_CYC_HOME_AIR_TEMP_TARGET"),
            "supply_air_target_away": data.get("A_CYC_AWAY_AIR_TEMP_TARGET"),
            "supply_air_target_boost": data.get("A_CYC_BOOST_AIR_TEMP_TARGET"),
            # Other sensors
            "humidity": data.get("A_CYC_RH_VALUE"),
            "efficiency": efficiency,
            "co2": data.get("A_CYC_CO2_VALUE"),
            # Binary sensor
            "post_heater": data.get("A_CYC_IO_HEATER") == 1,
            # Switch
            "bypass_locked": data.get("A_CYC_BYPASS_LOCKED") == 1,
        })

        return attributes

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
        except HeliosApiException as err:
            raise HomeAssistantError("Failed to set power mode") from err

        return True

    async def _async_set_preset_mode_internal(self, preset_mode: str) -> bool:
        """Set new preset mode.

        Returns true if the mode has been changed, false otherwise.
        """
        if preset_mode == self.preset_mode:
            return False

        try:
            profile = PRESET_MODE_TO_HELIOS_PROFILE[preset_mode]
            await self._client.set_profile(profile)

        except HeliosApiException as err:
            raise HomeAssistantError(f"Failed to set profile: {preset_mode}") from err

        return True

    async def _async_set_percentage_internal(
        self, percentage: int, preset_mode: str | None = None
    ) -> bool:
        """Set fan speed percentage for current profile.

        Returns true if speed has been changed, false otherwise.
        """
        helios_profile = (
            PRESET_MODE_TO_HELIOS_PROFILE[preset_mode]
            if preset_mode is not None
            else self.coordinator.data.profile
        )

        try:
            await self._client.set_fan_speed(helios_profile, percentage)
        except HeliosInvalidInputException as err:
            # This can happen if current profile does not support setting the fan speed.
            raise ValueError(
                f"{helios_profile} profile does not support setting the fan speed"
            ) from err
        except HeliosApiException as err:
            raise HomeAssistantError("Failed to set fan speed") from err

        return True
