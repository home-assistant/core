"""Switches on Zigbee Home Automation networks."""
import logging

from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.const import STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .core.const import (
    DATA_ZHA, DATA_ZHA_DISPATCHERS, ZHA_DISCOVERY_NEW, ON_OFF_CHANNEL,
    SIGNAL_ATTR_UPDATED
)
from .entity import ZhaEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Old way of setting up Zigbee Home Automation switches."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation switch from config entry."""
    async def async_discover(discovery_info):
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    [discovery_info])

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(DOMAIN), async_discover)
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    switches = hass.data.get(DATA_ZHA, {}).get(DOMAIN)
    if switches is not None:
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    switches.values())
        del hass.data[DATA_ZHA][DOMAIN]


async def _async_setup_entities(hass, config_entry, async_add_entities,
                                discovery_infos):
    """Set up the ZHA switches."""
    entities = []
    for discovery_info in discovery_infos:
        entities.append(Switch(**discovery_info))

    async_add_entities(entities, update_before_add=True)


class Switch(ZhaEntity, SwitchDevice):
    """ZHA switch."""

    _domain = DOMAIN

    def __init__(self, **kwargs):
        """Initialize the ZHA switch."""
        super().__init__(**kwargs)
        self._on_off_channel = self.cluster_channels.get(ON_OFF_CHANNEL)

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        if self._state is None:
            return False
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        success = await self._on_off_channel.on()
        if not success:
            return
        self._state = True
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        success = await self._on_off_channel.off()
        if not success:
            return
        self._state = False
        self.async_schedule_update_ha_state()

    def async_set_state(self, state):
        """Handle state update from channel."""
        self._state = bool(state)
        self.async_schedule_update_ha_state()

    @property
    def device_state_attributes(self):
        """Return state attributes."""
        return self.state_attributes

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_accept_signal(
            self._on_off_channel, SIGNAL_ATTR_UPDATED, self.async_set_state)

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._state = last_state.state == STATE_ON

    async def async_update(self):
        """Attempt to retrieve on off state from the switch."""
        await super().async_update()
        if self._on_off_channel:
            self._state = await self._on_off_channel.get_attribute_value(
                'on_off')
