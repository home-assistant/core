"""
Cluster listeners for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""

import logging

_LOGGER = logging.getLogger(__name__)


def parse_and_log_command(entity_id, cluster, tsn, command_id, args):
    """Parse and log a zigbee cluster command."""
    cmd = cluster.server_commands.get(command_id, [command_id])[0]
    _LOGGER.debug(
        "%s: received '%s' command with %s args on cluster_id '%s' tsn '%s'",
        entity_id,
        cmd,
        args,
        cluster.cluster_id,
        tsn
    )
    return cmd


class ClusterListener:
    """Listener for a Zigbee cluster."""

    def __init__(self, entity, cluster):
        """Initialize ClusterListener."""
        self._entity = entity
        self._cluster = cluster

    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        pass

    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        pass

    def zdo_command(self, *args, **kwargs):
        """Handle ZDO commands on this cluster."""
        pass

    def zha_send_event(self, cluster, command, args):
        """Relay entity events to hass."""
        pass  # don't let entities fire events


class OnOffListener(ClusterListener):
    """Listener for the OnOff Zigbee cluster."""

    ON_OFF = 0

    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        cmd = parse_and_log_command(
            self._entity.entity_id,
            self._cluster,
            tsn,
            command_id,
            args
        )

        if cmd in ('off', 'off_with_effect'):
            self._entity.set_state(False)
        elif cmd in ('on', 'on_with_recall_global_scene', 'on_with_timed_off'):
            self._entity.set_state(True)
        elif cmd == 'toggle':
            self._entity.set_state(not self._entity.is_on)

    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == self.ON_OFF:
            self._entity.set_state(bool(value))


class LevelListener(ClusterListener):
    """Listener for the LevelControl Zigbee cluster."""

    CURRENT_LEVEL = 0

    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        cmd = parse_and_log_command(
            self._entity.entity_id,
            self._cluster,
            tsn,
            command_id,
            args
        )

        if cmd in ('move_to_level', 'move_to_level_with_on_off'):
            self._entity.set_level(args[0])
        elif cmd in ('move', 'move_with_on_off'):
            # We should dim slowly -- for now, just step once
            rate = args[1]
            if args[0] == 0xff:
                rate = 10  # Should read default move rate
            self._entity.move_level(-rate if args[0] else rate)
        elif cmd in ('step', 'step_with_on_off'):
            # Step (technically may change on/off)
            self._entity.move_level(-args[1] if args[0] else args[1])

    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == self.CURRENT_LEVEL:
            self._entity.set_level(value)
