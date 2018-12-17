"""
Cluster listeners for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""


class ClusterListener:
    """Listener for a Zigbee cluster."""

    def __init__(self, entity):
        """Initialize OnOffListener."""
        self._entity = entity

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

    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        if command_id in (0x0000, 0x0040):
            self._entity.set_state(False)
        elif command_id in (0x0001, 0x0041, 0x0042):
            self._entity.set_state(True)
        elif command_id == 0x0002:
            self._entity.set_state(not self._entity.is_on)

    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == 0:
            self._entity.set_state(value)


class LevelListener(ClusterListener):
    """Listener for the LevelControl Zigbee cluster."""

    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        if command_id in (0x0000, 0x0004):  # move_to_level, -with_on_off
            self._entity.set_level(args[0])
        elif command_id in (0x0001, 0x0005):  # move, -with_on_off
            # We should dim slowly -- for now, just step once
            rate = args[1]
            if args[0] == 0xff:
                rate = 10  # Should read default move rate
            self._entity.move_level(-rate if args[0] else rate)
        elif command_id in (0x0002, 0x0006):  # step, -with_on_off
            # Step (technically may change on/off)
            self._entity.move_level(-args[1] if args[0] else args[1])

    def attribute_updated(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == 0:
            self._entity.set_level(value)
