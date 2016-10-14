"""
Support for RFXtrx roller shutter components.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/rollershutter.rfxtrx/
"""

import homeassistant.components.rfxtrx as rfxtrx
from homeassistant.components.rollershutter import RollershutterDevice

DEPENDENCIES = ['rfxtrx']

PLATFORM_SCHEMA = rfxtrx.DEFAULT_SCHEMA


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the Demo roller shutters."""
    import RFXtrx as rfxtrxmod

    # Add rollershutter from config file
    rollershutters = rfxtrx.get_devices_from_config(config,
                                                    RfxtrxRollershutter)
    add_devices_callback(rollershutters)

    def rollershutter_update(event):
        """Callback for roller shutter updates from the RFXtrx gateway."""
        if not isinstance(event.device, rfxtrxmod.LightingDevice) or \
                event.device.known_to_be_dimmable or \
                not event.device.known_to_be_rollershutter:
            return

        new_device = rfxtrx.get_new_device(event, config, RfxtrxRollershutter)
        if new_device:
            add_devices_callback([new_device])

        rfxtrx.apply_received_command(event)

    # Subscribe to main rfxtrx events
    if rollershutter_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(rollershutter_update)


# pylint: disable=abstract-method
class RfxtrxRollershutter(rfxtrx.RfxtrxDevice, RollershutterDevice):
    """Representation of an rfxtrx roller shutter."""

    @property
    def should_poll(self):
        """No polling available in rfxtrx roller shutter."""
        return False

    @property
    def current_position(self):
        """No position available in rfxtrx roller shutter."""
        return None

    def move_up(self, **kwargs):
        """Move the roller shutter up."""
        self._send_command("roll_up")

    def move_down(self, **kwargs):
        """Move the roller shutter down."""
        self._send_command("roll_down")

    def stop(self, **kwargs):
        """Stop the roller shutter."""
        self._send_command("stop_roll")
