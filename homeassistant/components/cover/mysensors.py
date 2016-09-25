"""
Support for MySensors covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.mysensors/
"""
import logging

from homeassistant.components import mysensors
from homeassistant.components.cover import CoverDevice, ATTR_POSITION

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the mysensors platform for covers."""
    if discovery_info is None:
        return
    for gateway in mysensors.GATEWAYS.values():
        if float(gateway.protocol_version) < 1.5:
            continue
        pres = gateway.const.Presentation
        set_req = gateway.const.SetReq
        map_sv_types = {
            pres.S_COVER: [set_req.V_PERCENTAGE],
        }
        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, add_devices, MySensorsCover))


class MySensorsCover(mysensors.MySensorsDeviceEntity, CoverDevice):
    """Representation of the value of a MySensors Cover child node."""

    @property
    def assumed_state(self):
        """Return True if unable to access real state of entity."""
        return self.gateway.optimistic

    def update(self):
        """Update the controller with the latest value from a sensor."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        set_req = self.gateway.const.SetReq
        for value_type, value in child.values.items():
            _LOGGER.debug(
                '%s: value_type %s, value = %s', self._name, value_type, value)
            if value_type == set_req.V_PERCENTAGE:
                self._values[value_type] = int(value)
            else:
                self._values[value_type] = value

    @property
    def is_closed(self):
        """Return True if cover is closed."""
        set_req = self.gateway.const.SetReq
        return self._values.get(set_req.V_PERCENTAGE) == 0

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        set_req = self.gateway.const.SetReq
        return self._values.get(set_req.V_PERCENTAGE)

    def open_cover(self, **kwargs):
        """Move the cover up."""
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_UP, 1)
        if self.gateway.optimistic:
            # Optimistically assume that cover has changed state.
            self._values[set_req.V_PERCENTAGE] = 100
            self.update_ha_state()

    def close_cover(self, **kwargs):
        """Move the cover down."""
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_DOWN, 1)
        if self.gateway.optimistic:
            # Optimistically assume that cover has changed state.
            self._values[set_req.V_PERCENTAGE] = 0
            self.update_ha_state()

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs.get(ATTR_POSITION)
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_PERCENTAGE, position)
        if self.gateway.optimistic:
            # Optimistically assume that cover has changed state.
            self._values[set_req.V_PERCENTAGE] = position
            self.update_ha_state()

    def stop_cover(self, **kwargs):
        """Stop the device."""
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_STOP, 1)
