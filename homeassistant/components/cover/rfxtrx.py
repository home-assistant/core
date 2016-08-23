"""
Support for RFXtrx cover components.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/cover.rfxtrx/
"""

import homeassistant.components.rfxtrx as rfxtrx
from homeassistant.components.cover import CoverDevice

DEPENDENCIES = ['rfxtrx']

PLATFORM_SCHEMA = rfxtrx.DEFAULT_SCHEMA


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the RFXtrx cover."""
    import RFXtrx as rfxtrxmod

    # Add cover from config file
    covers = rfxtrx.get_devices_from_config(config,
                                            RfxtrxCover)
    add_devices_callback(covers)

    def cover_update(event):
        """Callback for cover updates from the RFXtrx gateway."""
        if not isinstance(event.device, rfxtrxmod.LightingDevice) or \
                event.device.known_to_be_dimmable or \
                not event.device.known_to_be_rollershutter:
            return

        new_device = rfxtrx.get_new_device(event, config, RfxtrxCover)
        if new_device:
            add_devices_callback([new_device])

        rfxtrx.apply_received_command(event)

    # Subscribe to main rfxtrx events
    if cover_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(cover_update)


# pylint: disable=abstract-method
class RfxtrxCover(rfxtrx.RfxtrxDevice, CoverDevice):
    """Representation of an rfxtrx cover."""

    @property
    def should_poll(self):
        """No polling available in rfxtrx cover."""
        return False

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return None

    def open_cover(self, **kwargs):
        """Move the cover up."""
        self._send_command("roll_up")

    def close_cover(self, **kwargs):
        """Move the cover down."""
        self._send_command("roll_down")

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._send_command("stop_roll")
