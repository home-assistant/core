"""Fans on Zigbee Home Automation networks."""
import functools
import logging
from typing import List

from zigpy.exceptions import DeliveryError
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

_LOGGER = logging.getLogger(__name__)

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

VALUE_TO_SPEED = dict(enumerate(SPEED_LIST))
SPEED_TO_VALUE = {speed: i for i, speed in enumerate(SPEED_LIST)}
STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, DOMAIN)
GROUP_MATCH = functools.partial(ZHA_ENTITIES.group_match, DOMAIN)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation fan from config entry."""
    entities_to_create = hass.data[DATA_ZHA][DOMAIN]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
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
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return SPEED_LIST

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return self._state

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        if self._state is None:
            return False
        return self._state != SPEED_OFF

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn the entity on."""
        if speed is None:
            speed = SPEED_MEDIUM

        await self.async_set_speed(speed)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        await self.async_set_speed(SPEED_OFF)

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        await self._fan_channel.async_set_speed(SPEED_TO_VALUE[speed])
        self.async_set_state(0, "fan_mode", speed)

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
        await self.async_accept_signal(
            self._fan_channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._state = VALUE_TO_SPEED.get(last_state.state, last_state.state)

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Handle state update from channel."""
        self._state = VALUE_TO_SPEED.get(value, self._state)
        self.async_write_ha_state()

    async def async_update(self):
        """Attempt to retrieve on off state from the fan."""
        await super().async_update()
        if self._fan_channel:
            state = await self._fan_channel.get_attribute_value("fan_mode")
            if state is not None:
                self._state = VALUE_TO_SPEED.get(state, self._state)


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

        # what should we do with this hack?
        async def async_set_speed(value) -> None:
            """Set the speed of the fan."""
            try:
                await self._fan_channel.write_attributes({"fan_mode": value})
            except DeliveryError as ex:
                self.error("Could not set speed: %s", ex)
                return

        self._fan_channel.async_set_speed = async_set_speed

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
            self._state = states[0].state
