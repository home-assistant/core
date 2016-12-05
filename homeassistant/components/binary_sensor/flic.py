"""
Support for flic buttons.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/flic/
"""
import logging

# pylint: disable=import-error
import fliclib

from homeassistant.components import flic
from homeassistant.components.binary_sensor import (
    DOMAIN,
    BinarySensorDevice)

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []

EVENT_BUTTON_ACTIVATED = "button_activated"
ATTR_CLICK_TYPE = "click_type"

CLICK_TYPES = {
    fliclib.ClickType.ButtonSingleClick: "single",
    fliclib.ClickType.ButtonDoubleClick: "double",
    fliclib.ClickType.ButtonHold: "hold",
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Flic platform for binary sensors."""
    if discovery_info is None or flic.CLIENT is None:
        return

    add_devices([FlicEntity(discovery_info[flic.ATTR_BD_ADDR])])


class FlicEntity(BinarySensorDevice):
    """Representation of a Flic button."""

    def __init__(self, bd_addr):
        """Initialize the sensor."""
        self._cc = fliclib.ButtonConnectionChannel(bd_addr)
        self._cc.on_connection_status_changed = self.on_status_changed
        self._cc.on_button_single_or_double_click_or_hold = \
            self.on_button_event
        self._status = fliclib.ConnectionStatus.Disconnected
        self.entity_id = "{}.{}".format(DOMAIN, self.name)

        flic.CLIENT.add_connection_channel(self._cc)
        _LOGGER.info("Flic Button Added: %s", bd_addr)

    def on_status_changed(
            self, channel, connection_status, disconnect_reason):
        """Button connection status changed."""
        self._status = connection_status
        self.schedule_update_ha_state()

    def on_button_event(self, channel, click_type, was_queued, time_diff):
        """Button clicked event."""
        self.hass.bus.fire(
            EVENT_BUTTON_ACTIVATED, {ATTR_CLICK_TYPE: CLICK_TYPES[click_type]})

    @property
    def name(self):
        """Return the name of the device."""
        return "flic_{}".format(self._cc.bd_addr.replace(":", ""))

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return (
            self._status == fliclib.ConnectionStatus.Ready or
            self._status == fliclib.ConnectionStatus.Connected)

    @property
    def should_poll(self):
        """No polling needed."""
        return False
