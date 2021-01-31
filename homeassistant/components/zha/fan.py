"""Fans on Zigbee Home Automation networks."""
import functools
import math
from typing import List, Optional

from zigpy.exceptions import ZigbeeException
import zigpy.zcl.clusters.hvac as hvac

from homeassistant.components.fan import (
    DOMAIN,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.percentage import (
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
SPEED_ON = "on"
# The fan speed is self-regulated
SPEED_AUTO = "auto"
# When the heated/cooled space is occupied, the fan is always on
SPEED_SMART = "smart"

SPEED_LIST = [
    SPEED_OFF,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_HIGH,
    SPEED_ON,
    SPEED_AUTO,
    SPEED_SMART,
]

SPEED_RANGE = (1, 3)  # off is not included
PRESET_MODES_TO_NAME = {5: SPEED_AUTO, 6: SPEED_SMART}
NAME_TO_PRESET_MODE = {v: k for k, v in PRESET_MODES_TO_NAME.items()}
PRESET_MODES = list(NAME_TO_PRESET_MODE)
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

    def __init__(self, *args, **kwargs):
        """Initialize the fan."""
        super().__init__(*args, **kwargs)
        self._state = None
        self._fan_channel = None

    @property
    def percentage(self) -> str:
        """Return the current speed percentage."""
        if self._state is None or self._state > SPEED_RANGE[1]:
            return None
        if self._state == 0:
            return 0
        return ranged_value_to_percentage(SPEED_RANGE, self._state)

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        return PRESET_MODES_TO_NAME.get(self._state)

    @property
    def preset_modes(self) -> str:
        """Return the available preset modes."""
        return PRESET_MODES

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    async def async_turn_on(
        self, speed=None, percentage=None, preset_mode=None, **kwargs
    ) -> None:
        """Turn the entity on."""
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        await self.async_set_percentage(0)

    async def async_set_percentage(self, percentage: Optional[int]) -> None:
        """Set the speed percenage of the fan."""
        if percentage is None:
            percentage = 50
        fan_mode = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        await self._async_set_fan_mode(fan_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the speed percenage of the fan."""
        fan_mode = NAME_TO_PRESET_MODE.get(preset_mode)
        await self._async_set_fan_mode(fan_mode)

    async def _async_set_fan_mode(self, fan_mode: int) -> None:
        """Set the fan mode for the fan."""
        await self._fan_channel.async_set_speed(fan_mode)
        self.async_set_state(0, "fan_mode", fan_mode)

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
    def percentage(self) -> str:
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
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        return PRESET_MODES_TO_NAME.get(self._fan_channel.fan_mode)

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Handle state update from channel."""
        self.async_write_ha_state()


@GROUP_MATCH()
class FanGroup(BaseFan, ZhaGroupEntity):
    """Representation of a fan group."""

    def __init__(
        self, entity_ids: List[str], unique_id: str, group_id: int, zha_device, **kwargs
    ) -> None:
        """Initialize a fan group."""
        super().__init__(entity_ids, unique_id, group_id, zha_device, **kwargs)
        self._available: bool = False
        group = self.zha_device.gateway.get_group(self._group_id)
        self._fan_channel = group.endpoint[hvac.Fan.cluster_id]

    async def async_set_percentage(self, percentage: Optional[int]) -> None:
        """Set the speed percenage of the fan."""
        if percentage is None:
            percentage = 50
        fan_mode = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        await self._async_set_fan_mode(fan_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the speed percenage of the fan."""
        fan_mode = NAME_TO_PRESET_MODE.get(preset_mode)
        await self._async_set_fan_mode(fan_mode)

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
        states: List[State] = list(filter(None, all_states))
        on_states: List[State] = [state for state in states if state.state != SPEED_OFF]

        self._available = any(state.state != STATE_UNAVAILABLE for state in states)
        # for now just use first non off state since its kind of arbitrary
        if not on_states:
            self._state = SPEED_OFF
        else:
            self._state = on_states[0].state

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await self.async_update()
        await super().async_added_to_hass()
