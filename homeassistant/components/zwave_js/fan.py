"""Support for Z-Wave fans."""
from __future__ import annotations

import math
from typing import Any, cast

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import TARGET_VALUE_PROPERTY

from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
    NotValidPresetModeError,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DATA_CLIENT, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .discovery_data_template import FanValueMapping, FanValueMappingDataTemplate
from .entity import ZWaveBaseEntity

DEFAULT_SPEED_RANGE = (1, 99)  # off is not included


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave Fan from Config Entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_fan(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave fan."""
        entities: list[ZWaveBaseEntity] = []
        if info.platform_hint == "has_fan_value_mapping":
            entities.append(ValueMappingZwaveFan(config_entry, client, info))
        else:
            entities.append(ZwaveFan(config_entry, client, info))

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

    def __init__(
        self, config_entry: ConfigEntry, client: ZwaveClient, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize the fan."""
        super().__init__(config_entry, client, info)
        self._target_value = self.get_zwave_value(TARGET_VALUE_PROPERTY)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            zwave_speed = 0
        else:
            zwave_speed = math.ceil(
                percentage_to_ranged_value(DEFAULT_SPEED_RANGE, percentage)
            )

        await self.info.node.async_set_value(self._target_value, zwave_speed)

    async def async_turn_on(
        self,
        speed: str | None = None,
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
            # Value 255 tells device to return to previous value
            await self.info.node.async_set_value(self._target_value, 255)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.info.node.async_set_value(self._target_value, 0)

    @property
    def is_on(self) -> bool | None:  # type: ignore
        """Return true if device is on (speed above 0)."""
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

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(DEFAULT_SPEED_RANGE)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED


class ValueMappingZwaveFan(ZwaveFan):
    """A Zwave fan with a value mapping data (e.g., 1-24 is low)."""

    def __init__(
        self, config_entry: ConfigEntry, client: ZwaveClient, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize the fan."""
        super().__init__(config_entry, client, info)
        self.data_template = cast(
            FanValueMappingDataTemplate, self.info.platform_data_template
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        zwave_speed = self.percentage_to_zwave_speed(percentage)
        await self.info.node.async_set_value(self._target_value, zwave_speed)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        for zwave_value, mapped_preset_mode in self.fan_value_mapping.presets.items():
            if preset_mode == mapped_preset_mode:
                await self.info.node.async_set_value(self._target_value, zwave_value)
                return

        raise NotValidPresetModeError(
            f"The preset_mode {preset_mode} is not a valid preset_mode: {self.preset_modes}"
        )

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
        return list(self.fan_value_mapping.presets.values())

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self.fan_value_mapping.presets.get(self.info.primary_value.value)

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
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = SUPPORT_SET_SPEED

        if self.fan_value_mapping.presets:
            flags |= SUPPORT_PRESET_MODE

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
                return max_speed

        # This shouldn't actually happen; the last entry in
        # `self.fan_value_mapping.speeds` should map to 100%.
        (_, last_max_speed) = self.fan_value_mapping.speeds[-1]
        return last_max_speed

    def zwave_speed_to_percentage(self, zwave_speed: int) -> int | None:
        """
        Convert a Zwave speed to a percentage.

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
