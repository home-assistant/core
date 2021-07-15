"""Fans on Zigbee Home Automation networks."""
from __future__ import annotations

from abc import abstractmethod
import functools
import math

from zigpy.exceptions import ZigbeeException
from zigpy.zcl.clusters import hvac

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN,
    SUPPORT_SET_SPEED,
    FanEntity,
    NotValidPresetModeError,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .core import discovery
from .core.const import (
    CHANNEL_FAN,
    DATA_ZHA,
    DATA_ZHA_DISPATCHERS,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity, ZhaGroupEntity

# Additional speeds in zigbee's ZCL
# Spec is unclear as to what this value means. On King Of Fans HBUniversal
# receiver, this means Very High.
PRESET_MODE_ON = "on"
# The fan speed is self-regulated
PRESET_MODE_AUTO = "auto"
# When the heated/cooled space is occupied, the fan is always on
PRESET_MODE_SMART = "smart"

SPEED_RANGE = (1, 3)  # off is not included
PRESET_MODES_TO_NAME = {4: PRESET_MODE_ON, 5: PRESET_MODE_AUTO, 6: PRESET_MODE_SMART}

NAME_TO_PRESET_MODE = {v: k for k, v in PRESET_MODES_TO_NAME.items()}
PRESET_MODES = list(NAME_TO_PRESET_MODE)

DEFAULT_ON_PERCENTAGE = 50

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, DOMAIN)
GROUP_MATCH = functools.partial(ZHA_ENTITIES.group_match, DOMAIN)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation fan from config entry."""
    entities_to_create = hass.data[DATA_ZHA][DOMAIN]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities,
            async_add_entities,
            entities_to_create,
            update_before_add=False,
        ),
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)


class BaseFan(FanEntity):
    """Base representation of a ZHA fan."""

    @property
    def preset_modes(self) -> list[str]:
        """Return the available preset modes."""
        return PRESET_MODES

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    async def async_turn_on(
        self, speed=None, percentage=None, preset_mode=None, **kwargs
    ) -> None:
        """Turn the entity on."""
        if percentage is None:
            percentage = DEFAULT_ON_PERCENTAGE
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        await self.async_set_percentage(0)

    async def async_set_percentage(self, percentage: int | None) -> None:
        """Set the speed percenage of the fan."""
        fan_mode = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        await self._async_set_fan_mode(fan_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode for the fan."""
        if preset_mode not in self.preset_modes:
            raise NotValidPresetModeError(
                f"The preset_mode {preset_mode} is not a valid preset_mode: {self.preset_modes}"
            )
        await self._async_set_fan_mode(NAME_TO_PRESET_MODE[preset_mode])

    @abstractmethod
    async def _async_set_fan_mode(self, fan_mode: int) -> None:
        """Set the fan mode for the fan."""

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Handle state update from channel."""


@STRICT_MATCH(channel_names=CHANNEL_FAN)
class ZhaFan(BaseFan, ZhaEntity):
    """Representation of a ZHA fan."""

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Init this sensor."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._fan_channel = self.cluster_channels.get(CHANNEL_FAN)

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._fan_channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if (
            self._fan_channel.fan_mode is None
            or self._fan_channel.fan_mode > SPEED_RANGE[1]
        ):
            return None
        if self._fan_channel.fan_mode == 0:
            return 0
        return ranged_value_to_percentage(SPEED_RANGE, self._fan_channel.fan_mode)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return PRESET_MODES_TO_NAME.get(self._fan_channel.fan_mode)

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Handle state update from channel."""
        self.async_write_ha_state()

    async def _async_set_fan_mode(self, fan_mode: int) -> None:
        """Set the fan mode for the fan."""
        await self._fan_channel.async_set_speed(fan_mode)
        self.async_set_state(0, "fan_mode", fan_mode)


@GROUP_MATCH()
class FanGroup(BaseFan, ZhaGroupEntity):
    """Representation of a fan group."""

    def __init__(
        self, entity_ids: list[str], unique_id: str, group_id: int, zha_device, **kwargs
    ) -> None:
        """Initialize a fan group."""
        super().__init__(entity_ids, unique_id, group_id, zha_device, **kwargs)
        self._available: bool = False
        group = self.zha_device.gateway.get_group(self._group_id)
        self._fan_channel = group.endpoint[hvac.Fan.cluster_id]
        self._percentage = None
        self._preset_mode = None

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        return self._percentage

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._preset_mode

    async def _async_set_fan_mode(self, fan_mode: int) -> None:
        """Set the fan mode for the group."""
        try:
            await self._fan_channel.write_attributes({"fan_mode": fan_mode})
        except ZigbeeException as ex:
            self.error("Could not set fan mode: %s", ex)
        self.async_set_state(0, "fan_mode", fan_mode)

    async def async_update(self):
        """Attempt to retrieve on off state from the fan."""
        all_states = [self.hass.states.get(x) for x in self._entity_ids]
        states: list[State] = list(filter(None, all_states))
        percentage_states: list[State] = [
            state for state in states if state.attributes.get(ATTR_PERCENTAGE)
        ]
        preset_mode_states: list[State] = [
            state for state in states if state.attributes.get(ATTR_PRESET_MODE)
        ]
        self._available = any(state.state != STATE_UNAVAILABLE for state in states)

        if percentage_states:
            self._percentage = percentage_states[0].attributes[ATTR_PERCENTAGE]
            self._preset_mode = None
        elif preset_mode_states:
            self._preset_mode = preset_mode_states[0].attributes[ATTR_PRESET_MODE]
            self._percentage = None
        else:
            self._percentage = None
            self._preset_mode = None

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await self.async_update()
        await super().async_added_to_hass()
