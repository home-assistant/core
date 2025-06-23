"""Support for Z-Wave fans."""

from __future__ import annotations

import math
from typing import Any, cast

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import TARGET_VALUE_PROPERTY, CommandClass
from zwave_js_server.const.command_class.multilevel_switch import SET_TO_PREVIOUS_VALUE
from zwave_js_server.const.command_class.thermostat import (
    THERMOSTAT_FAN_OFF_PROPERTY,
    THERMOSTAT_FAN_STATE_PROPERTY,
)
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.value import Value as ZwaveValue

from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DATA_CLIENT, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .discovery_data_template import FanValueMapping, FanValueMappingDataTemplate
from .entity import ZWaveBaseEntity
from .helpers import get_value_of_zwave_value

PARALLEL_UPDATES = 0

DEFAULT_SPEED_RANGE = (1, 99)  # off is not included

ATTR_FAN_STATE = "fan_state"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Z-Wave Fan from Config Entry."""
    client: ZwaveClient = config_entry.runtime_data[DATA_CLIENT]

    @callback
    def async_add_fan(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave fan."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[ZWaveBaseEntity] = []
        if info.platform_hint == "has_fan_value_mapping":
            entities.append(ValueMappingZwaveFan(config_entry, driver, info))
        elif info.platform_hint == "thermostat_fan":
            entities.append(ZwaveThermostatFan(config_entry, driver, info))
        else:
            entities.append(ZwaveFan(config_entry, driver, info))

        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{FAN_DOMAIN}",
            async_add_fan,
        )
    )


class ZwaveFan(ZWaveBaseEntity, FanEntity):
    """Representation of a Z-Wave fan."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )

    def __init__(
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize the fan."""
        super().__init__(config_entry, driver, info)
        target_value = self.get_zwave_value(TARGET_VALUE_PROPERTY)
        assert target_value
        self._target_value = target_value

        self._use_optimistic_state: bool = False

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            zwave_speed = 0
        else:
            zwave_speed = math.ceil(
                percentage_to_ranged_value(DEFAULT_SPEED_RANGE, percentage)
            )

        await self._async_set_value(self._target_value, zwave_speed)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
        elif preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        else:
            if self.info.primary_value.command_class != CommandClass.SWITCH_MULTILEVEL:
                raise HomeAssistantError(
                    "`percentage` or `preset_mode` must be provided"
                )
            # If this is a Multilevel Switch CC value, we do an optimistic state update
            # when setting to a previous value to avoid waiting for the value to be
            # updated from the device which is typically delayed and causes a confusing
            # UX.
            await self._async_set_value(self._target_value, SET_TO_PREVIOUS_VALUE)
            self._use_optimistic_state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._async_set_value(self._target_value, 0)

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on (speed above 0)."""
        if self._use_optimistic_state:
            self._use_optimistic_state = False
            return True
        if self.info.primary_value.value is None:
            # guard missing value
            return None
        return bool(self.info.primary_value.value > 0)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self.info.primary_value.value is None:
            # guard missing value
            return None
        return ranged_value_to_percentage(
            DEFAULT_SPEED_RANGE, self.info.primary_value.value
        )

    @property
    def percentage_step(self) -> float:
        """Return the step size for percentage."""
        return 1


class ValueMappingZwaveFan(ZwaveFan):
    """A Zwave fan with a value mapping data (e.g., 1-24 is low)."""

    def __init__(
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize the fan."""
        super().__init__(config_entry, driver, info)
        self.data_template = cast(
            FanValueMappingDataTemplate, self.info.platform_data_template
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        zwave_speed = self.percentage_to_zwave_speed(percentage)
        await self._async_set_value(self._target_value, zwave_speed)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        for zwave_value, mapped_preset_mode in self.fan_value_mapping.presets.items():
            if preset_mode == mapped_preset_mode:
                await self._async_set_value(self._target_value, zwave_value)
                return

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available and self.has_fan_value_mapping

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self.info.primary_value.value is None:
            # guard missing value
            return None

        if self.preset_mode is not None:
            return None

        return self.zwave_speed_to_percentage(self.info.primary_value.value)

    @property
    def percentage_step(self) -> float:
        """Return the step size for percentage."""
        # This is the same implementation as the base fan type, but
        # it needs to be overridden here because the ZwaveFan does
        # something different for fans with unknown speeds.
        return 100 / self.speed_count

    @property
    def preset_modes(self) -> list[str]:
        """Return the available preset modes."""
        if not self.has_fan_value_mapping:
            return []

        return list(self.fan_value_mapping.presets.values())

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if (value := self.info.primary_value.value) is None:
            return None
        return self.fan_value_mapping.presets.get(value)

    @property
    def has_fan_value_mapping(self) -> bool:
        """Check if the speed configuration is valid."""
        return (
            self.data_template.get_fan_value_mapping(self.info.platform_data)
            is not None
        )

    @property
    def fan_value_mapping(self) -> FanValueMapping:
        """Return the speed configuration for this fan."""
        fan_value_mapping = self.data_template.get_fan_value_mapping(
            self.info.platform_data
        )

        # Entity should be unavailable if this isn't set
        assert fan_value_mapping is not None

        return fan_value_mapping

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(self.fan_value_mapping.speeds)

    @property
    def supported_features(self) -> FanEntityFeature:
        """Flag supported features."""
        flags = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )
        if self.has_fan_value_mapping and self.fan_value_mapping.presets:
            flags |= FanEntityFeature.PRESET_MODE

        return flags

    def percentage_to_zwave_speed(self, percentage: int) -> int:
        """Map a percentage to a ZWave speed."""
        if percentage == 0:
            return 0

        # Since the percentage steps are computed with rounding, we have to
        # search to find the appropriate speed.
        for speed_range in self.fan_value_mapping.speeds:
            (_, max_speed) = speed_range
            step_percentage = self.zwave_speed_to_percentage(max_speed)

            # zwave_speed_to_percentage will only return None if
            # `self.fan_value_mapping.speeds` doesn't contain the
            # specified speed. This can't happen here, because
            # the input is coming from the same data structure.
            assert step_percentage

            if percentage <= step_percentage:
                break

        return max_speed

    def zwave_speed_to_percentage(self, zwave_speed: int) -> int | None:
        """Convert a Zwave speed to a percentage.

        This method may return None if the device's value mapping doesn't cover
        the specified Z-Wave speed.
        """
        if zwave_speed == 0:
            return 0

        percentage = 0.0
        for speed_range in self.fan_value_mapping.speeds:
            (min_speed, max_speed) = speed_range
            percentage += self.percentage_step
            if min_speed <= zwave_speed <= max_speed:
                # This choice of rounding function is to provide consistency with how
                # the UI handles steps e.g., for a 3-speed fan, you get steps at 33,
                # 67, and 100.
                return round(percentage)

        # The specified Z-Wave device value doesn't map to a defined speed.
        return None


class ZwaveThermostatFan(ZWaveBaseEntity, FanEntity):
    """Representation of a Z-Wave thermostat fan."""

    _fan_mode: ZwaveValue
    _fan_off: ZwaveValue | None = None
    _fan_state: ZwaveValue | None = None

    def __init__(
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize the thermostat fan."""
        super().__init__(config_entry, driver, info)

        self._fan_mode = self.info.primary_value

        self._fan_off = self.get_zwave_value(
            THERMOSTAT_FAN_OFF_PROPERTY,
            CommandClass.THERMOSTAT_FAN_MODE,
            add_to_watched_value_ids=True,
        )
        self._fan_state = self.get_zwave_value(
            THERMOSTAT_FAN_STATE_PROPERTY,
            CommandClass.THERMOSTAT_FAN_STATE,
            add_to_watched_value_ids=True,
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        if not self._fan_off:
            raise HomeAssistantError("Unhandled action turn_on")
        await self._async_set_value(self._fan_off, False)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if not self._fan_off:
            raise HomeAssistantError("Unhandled action turn_off")
        await self._async_set_value(self._fan_off, True)

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        if (value := get_value_of_zwave_value(self._fan_off)) is None:
            return None
        return not cast(bool, value)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., auto, smart, interval, favorite."""
        value = get_value_of_zwave_value(self._fan_mode)
        if value is None or str(value) not in self._fan_mode.metadata.states:
            return None
        return cast(str, self._fan_mode.metadata.states[str(value)])

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""

        try:
            new_state = next(
                int(state)
                for state, label in self._fan_mode.metadata.states.items()
                if label == preset_mode
            )
        except StopIteration:
            raise ValueError(f"Received an invalid fan mode: {preset_mode}") from None

        await self._async_set_value(self._fan_mode, new_state)

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes."""
        if not self._fan_mode.metadata.states:
            return None
        return list(self._fan_mode.metadata.states.values())

    @property
    def supported_features(self) -> FanEntityFeature:
        """Flag supported features."""
        if not self._fan_off:
            return FanEntityFeature.PRESET_MODE
        return (
            FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )

    @property
    def fan_state(self) -> str | None:
        """Return the current state, Idle, Running, etc."""
        value = get_value_of_zwave_value(self._fan_state)
        if (
            value is None
            or self._fan_state is None
            or str(value) not in self._fan_state.metadata.states
        ):
            return None
        return cast(str, self._fan_state.metadata.states[str(value)])

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the optional state attributes."""
        attrs = {}

        if state := self.fan_state:
            attrs[ATTR_FAN_STATE] = state

        return attrs
