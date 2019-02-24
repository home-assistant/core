"""
General channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from . import ZigbeeChannel, parse_and_log_command
from ..helpers import get_attr_id_by_name
from ..const import (
    SIGNAL_ATTR_UPDATED,
    SIGNAL_MOVE_LEVEL, SIGNAL_SET_LEVEL, SIGNAL_STATE_ATTR, BASIC_CHANNEL,
    ON_OFF_CHANNEL, LEVEL_CHANNEL, POWER_CONFIGURATION_CHANNEL
)

_LOGGER = logging.getLogger(__name__)


class OnOffChannel(ZigbeeChannel):
    """Channel for the OnOff Zigbee cluster."""

    ON_OFF = 0

    def __init__(self, cluster, device):
        """Initialize OnOffChannel."""
        super().__init__(cluster, device)
        self.name = ON_OFF_CHANNEL
        self._state = None

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        cmd = parse_and_log_command(
            self.unique_id,
            self._cluster,
            tsn,
            command_id,
            args
        )

        if cmd in ('off', 'off_with_effect'):
            self.attribute_updated(self.ON_OFF, False)
        elif cmd in ('on', 'on_with_recall_global_scene', 'on_with_timed_off'):
            self.attribute_updated(self.ON_OFF, True)
        elif cmd == 'toggle':
            self.attribute_updated(self.ON_OFF, not bool(self._state))

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == self.ON_OFF:
            async_dispatcher_send(
                self._zha_device.hass,
                "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
                value
            )
            self._state = bool(value)

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        self._state = bool(
            await self.get_attribute_value(self.ON_OFF, from_cache=from_cache))
        await super().async_initialize(from_cache)


class LevelControlChannel(ZigbeeChannel):
    """Channel for the LevelControl Zigbee cluster."""

    CURRENT_LEVEL = 0

    def __init__(self, cluster, device):
        """Initialize LevelControlChannel."""
        super().__init__(cluster, device)
        self.name = LEVEL_CHANNEL

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        cmd = parse_and_log_command(
            self.unique_id,
            self._cluster,
            tsn,
            command_id,
            args
        )

        if cmd in ('move_to_level', 'move_to_level_with_on_off'):
            self.dispatch_level_change(SIGNAL_SET_LEVEL, args[0])
        elif cmd in ('move', 'move_with_on_off'):
            # We should dim slowly -- for now, just step once
            rate = args[1]
            if args[0] == 0xff:
                rate = 10  # Should read default move rate
            self.dispatch_level_change(
                SIGNAL_MOVE_LEVEL, -rate if args[0] else rate)
        elif cmd in ('step', 'step_with_on_off'):
            # Step (technically may change on/off)
            self.dispatch_level_change(
                SIGNAL_MOVE_LEVEL, -args[1] if args[0] else args[1])

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        _LOGGER.debug("%s: received attribute: %s update with value: %i",
                      self.unique_id, attrid, value)
        if attrid == self.CURRENT_LEVEL:
            self.dispatch_level_change(SIGNAL_SET_LEVEL, value)

    def dispatch_level_change(self, command, level):
        """Dispatch level change."""
        async_dispatcher_send(
            self._zha_device.hass,
            "{}_{}".format(self.unique_id, command),
            level
        )

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.get_attribute_value(
            self.CURRENT_LEVEL, from_cache=from_cache)
        await super().async_initialize(from_cache)


class BasicChannel(ZigbeeChannel):
    """Channel to interact with the basic cluster."""

    UNKNOWN = 0
    BATTERY = 3

    POWER_SOURCES = {
        UNKNOWN: 'Unknown',
        1: 'Mains (single phase)',
        2: 'Mains (3 phase)',
        BATTERY: 'Battery',
        4: 'DC source',
        5: 'Emergency mains constantly powered',
        6: 'Emergency mains and transfer switch'
    }

    def __init__(self, cluster, device):
        """Initialize BasicChannel."""
        super().__init__(cluster, device)
        self.name = BASIC_CHANNEL
        self._power_source = None

    async def async_configure(self):
        """Configure this channel."""
        await super().async_configure()
        await self.async_initialize(False)

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        self._power_source = await self.get_attribute_value(
            'power_source', from_cache=from_cache)
        await super().async_initialize(from_cache)

    def get_power_source(self):
        """Get the power source."""
        return self._power_source


class PowerConfigurationChannel(ZigbeeChannel):
    """Channel for the zigbee power configuration cluster."""

    def __init__(self, cluster, device):
        """Initialize PowerConfigurationChannel."""
        super().__init__(cluster, device)
        self.name = POWER_CONFIGURATION_CHANNEL

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        attr = self._report_config[1].get('attr')
        if isinstance(attr, str):
            attr_id = get_attr_id_by_name(self.cluster, attr)
        else:
            attr_id = attr
        if attrid == attr_id:
            async_dispatcher_send(
                self._zha_device.hass,
                "{}_{}".format(self.unique_id, SIGNAL_STATE_ATTR),
                'battery_level',
                value
            )

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.async_read_state(from_cache)
        await super().async_initialize(from_cache)

    async def async_update(self):
        """Retrieve latest state."""
        await self.async_read_state(True)

    async def async_read_state(self, from_cache):
        """Read data from the cluster."""
        await self.get_attribute_value(
            'battery_size', from_cache=from_cache)
        await self.get_attribute_value(
            'battery_percentage_remaining', from_cache=from_cache)
        await self.get_attribute_value(
            'battery_voltage', from_cache=from_cache)
