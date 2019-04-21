"""
Fans on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/fan.zha/
"""
import logging

from homeassistant.core import callback
from homeassistant.components.fan import (
    DOMAIN, SPEED_HIGH, SPEED_LOW, SPEED_MEDIUM, SPEED_OFF, SUPPORT_SET_SPEED,
    FanEntity)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .core.const import (
    DATA_ZHA, DATA_ZHA_DISPATCHERS, ZHA_DISCOVERY_NEW, FAN_CHANNEL,
    SIGNAL_ATTR_UPDATED
)
from .entity import ZhaEntity

DEPENDENCIES = ['zha']

_LOGGER = logging.getLogger(__name__)

# Additional speeds in zigbee's ZCL
# Spec is unclear as to what this value means. On King Of Fans HBUniversal
# receiver, this means Very High.
SPEED_ON = 'on'
# The fan speed is self-regulated
SPEED_AUTO = 'auto'
# When the heated/cooled space is occupied, the fan is always on
SPEED_SMART = 'smart'

SPEED_LIST = [
    SPEED_OFF,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_HIGH,
    SPEED_ON,
    SPEED_AUTO,
    SPEED_SMART
]

VALUE_TO_SPEED = {i: speed for i, speed in enumerate(SPEED_LIST)}
SPEED_TO_VALUE = {speed: i for i, speed in enumerate(SPEED_LIST)}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Old way of setting up Zigbee Home Automation fans."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation fan from config entry."""
    async def async_discover(discovery_info):
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    [discovery_info])

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(DOMAIN), async_discover)
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    fans = hass.data.get(DATA_ZHA, {}).get(DOMAIN)
    if fans is not None:
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    fans.values())
        del hass.data[DATA_ZHA][DOMAIN]


async def _async_setup_entities(hass, config_entry, async_add_entities,
                                discovery_infos):
    """Set up the ZHA fans."""
    entities = []
    for discovery_info in discovery_infos:
        entities.append(ZhaFan(**discovery_info))

    async_add_entities(entities, update_before_add=True)


class ZhaFan(ZhaEntity, FanEntity):
    """Representation of a ZHA fan."""

    _domain = DOMAIN

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Init this sensor."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._fan_channel = self.cluster_channels.get(FAN_CHANNEL)

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_accept_signal(
            self._fan_channel, SIGNAL_ATTR_UPDATED, self.async_set_state)

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._state = VALUE_TO_SPEED.get(last_state.state, last_state.state)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

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
    def device_state_attributes(self):
        """Return state attributes."""
        return self.state_attributes

    def async_set_state(self, state):
        """Handle state update from channel."""
        self._state = VALUE_TO_SPEED.get(state, self._state)
        self.async_schedule_update_ha_state()

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
        self.async_set_state(speed)

    async def async_update(self):
        """Attempt to retrieve on off state from the fan."""
        await super().async_update()
        if self._fan_channel:
            state = await self._fan_channel.get_attribute_value('fan_mode')
            if state is not None:
                self._state = VALUE_TO_SPEED.get(state, self._state)
