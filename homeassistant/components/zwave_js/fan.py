"""Support for Z-Wave fans."""
from __future__ import annotations

import math
from typing import Any, cast

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import TARGET_VALUE_PROPERTY

from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    SUPPORT_SET_SPEED,
    FanEntity,
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
from .discovery_data_template import FanSpeedDataTemplate
from .entity import ZWaveBaseEntity

SUPPORTED_FEATURES = SUPPORT_SET_SPEED

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
        if info.platform_hint == "configured_fan_speed":
            entities.append(ConfiguredSpeedRangeZwaveFan(config_entry, client, info))
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

    async def async_set_percentage(self, percentage: int | None) -> None:
        """Set the speed percentage of the fan."""
        target_value = self.get_zwave_value(TARGET_VALUE_PROPERTY)

        if percentage is None:
            # Value 255 tells device to return to previous value
            zwave_speed = 255
        elif percentage == 0:
            zwave_speed = 0
        else:
            zwave_speed = math.ceil(
                percentage_to_ranged_value(DEFAULT_SPEED_RANGE, percentage)
            )

        await self.info.node.async_set_value(target_value, zwave_speed)

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        target_value = self.get_zwave_value(TARGET_VALUE_PROPERTY)
        await self.info.node.async_set_value(target_value, 0)

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
        return SUPPORTED_FEATURES


class ConfiguredSpeedRangeZwaveFan(ZwaveFan):
    """A Zwave fan with a configured speed range (e.g., 1-24 is low)."""

    def __init__(
        self, config_entry: ConfigEntry, client: ZwaveClient, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize the fan."""
        super().__init__(config_entry, client, info)
        self.data_template = cast(
            FanSpeedDataTemplate, self.info.platform_data_template
        )

    async def async_set_percentage(self, percentage: int | None) -> None:
        """Set the speed percentage of the fan."""
        target_value = self.get_zwave_value(TARGET_VALUE_PROPERTY)

        # Entity should be unavailable if this isn't set
        assert self.speed_configuration

        if percentage is None:
            # Value 255 tells device to return to previous value
            zwave_speed = 255
        elif percentage == 0:
            zwave_speed = 0
        else:
            assert 0 <= percentage <= 100
            zwave_speed = self.speed_configuration[
                math.ceil(percentage / self.percentage_step) - 1
            ]

        await self.info.node.async_set_value(target_value, zwave_speed)

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available and self.speed_configuration is not None

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self.info.primary_value.value is None:
            # guard missing value
            return None

        if self.info.primary_value.value == 0:
            return 0

        # Entity should be unavailable if this isn't set
        assert self.speed_configuration

        percentage = 0.0
        for speed_limit in self.speed_configuration:
            percentage += self.percentage_step
            if self.info.primary_value.value <= speed_limit:
                break

        return int(percentage)

    @property
    def percentage_step(self) -> float:
        """Return the step size for percentage."""
        # This is the same implementation as the base fan type, but
        # it needs to be overridden here because the ZwaveFan does
        # something different for fans with unknown speeds.
        return 100 / self.speed_count

    @property
    def speed_configuration(self) -> list[int] | None:
        """Return the speed configuration for this fan."""
        return self.data_template.get_speed_config(self.info.platform_data)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""

        # Entity should be unavailable if this isn't set
        assert self.speed_configuration

        return len(self.speed_configuration)
