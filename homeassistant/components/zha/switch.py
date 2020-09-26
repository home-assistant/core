"""Switches on Zigbee Home Automation networks."""
import functools
import logging
from typing import Any, List

from zigpy.zcl.clusters.general import OnOff
from zigpy.zcl.foundation import Status

from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .core import discovery
from .core.const import (
    CHANNEL_ON_OFF,
    DATA_ZHA,
    DATA_ZHA_DISPATCHERS,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity, ZhaGroupEntity

_LOGGER = logging.getLogger(__name__)
STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, DOMAIN)
GROUP_MATCH = functools.partial(ZHA_ENTITIES.group_match, DOMAIN)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation switch from config entry."""
    entities_to_create = hass.data[DATA_ZHA][DOMAIN]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)


class BaseSwitch(SwitchEntity):
    """Common base class for zha switches."""

    def __init__(self, *args, **kwargs):
        """Initialize the ZHA switch."""
        self._on_off_channel = None
        self._state = None
        super().__init__(*args, **kwargs)

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        if self._state is None:
            return False
        return self._state

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        result = await self._on_off_channel.on()
        if not isinstance(result, list) or result[1] is not Status.SUCCESS:
            return
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        result = await self._on_off_channel.off()
        if not isinstance(result, list) or result[1] is not Status.SUCCESS:
            return
        self._state = False
        self.async_write_ha_state()


@STRICT_MATCH(channel_names=CHANNEL_ON_OFF)
class Switch(BaseSwitch, ZhaEntity):
    """ZHA switch."""

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize the ZHA switch."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._on_off_channel = self.cluster_channels.get(CHANNEL_ON_OFF)

    @callback
    def async_set_state(self, attr_id: int, attr_name: str, value: Any):
        """Handle state update from channel."""
        self._state = bool(value)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._on_off_channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @callback
    def async_restore_last_state(self, last_state) -> None:
        """Restore previous state."""
        self._state = last_state.state == STATE_ON

    async def async_update(self) -> None:
        """Attempt to retrieve on off state from the switch."""
        await super().async_update()
        if self._on_off_channel:
            state = await self._on_off_channel.get_attribute_value("on_off")
            if state is not None:
                self._state = state


@GROUP_MATCH()
class SwitchGroup(BaseSwitch, ZhaGroupEntity):
    """Representation of a switch group."""

    def __init__(
        self, entity_ids: List[str], unique_id: str, group_id: int, zha_device, **kwargs
    ) -> None:
        """Initialize a switch group."""
        super().__init__(entity_ids, unique_id, group_id, zha_device, **kwargs)
        self._available: bool = False
        group = self.zha_device.gateway.get_group(self._group_id)
        self._on_off_channel = group.endpoint[OnOff.cluster_id]

    async def async_update(self) -> None:
        """Query all members and determine the light group state."""
        all_states = [self.hass.states.get(x) for x in self._entity_ids]
        states: List[State] = list(filter(None, all_states))
        on_states = [state for state in states if state.state == STATE_ON]

        self._state = len(on_states) > 0
        self._available = any(state.state != STATE_UNAVAILABLE for state in states)
