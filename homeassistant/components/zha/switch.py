"""Switches on Zigbee Home Automation networks."""
import functools
import logging

from zigpy.zcl.foundation import Status

from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.const import STATE_ON
from homeassistant.core import callback
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
from .entity import ZhaEntity

_LOGGER = logging.getLogger(__name__)
STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, DOMAIN)


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


@STRICT_MATCH(channel_names=CHANNEL_ON_OFF)
class Switch(ZhaEntity, SwitchDevice):
    """ZHA switch."""

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize the ZHA switch."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._on_off_channel = self.cluster_channels.get(CHANNEL_ON_OFF)

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        if self._state is None:
            return False
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        result = await self._on_off_channel.on()
        if not isinstance(result, list) or result[1] is not Status.SUCCESS:
            return
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        result = await self._on_off_channel.off()
        if not isinstance(result, list) or result[1] is not Status.SUCCESS:
            return
        self._state = False
        self.async_write_ha_state()

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Handle state update from channel."""
        self._state = bool(value)
        self.async_write_ha_state()

    @property
    def device_state_attributes(self):
        """Return state attributes."""
        return self.state_attributes

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_accept_signal(
            self._on_off_channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._state = last_state.state == STATE_ON

    async def async_update(self):
        """Attempt to retrieve on off state from the switch."""
        await super().async_update()
        if self._on_off_channel:
            state = await self._on_off_channel.get_attribute_value("on_off")
            if state is not None:
                self._state = state
