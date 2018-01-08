"""Implements a base class for all IHC devices."""
import asyncio
from xml.etree.ElementTree import Element


class IHCDevice:
    """Base class for all ihc devices."""

    def __init__(self, ihc, name, ihc_id, product: Element=None):
        """Initialize IHC attributes."""
        self.ihc = ihc
        self._name = name
        self.ihc_id = ihc_id
        if product:
            self.ihc_name = product.attrib['name']
            self.ihc_note = product.attrib['note']
            self.ihc_position = product.attrib['position']
        else:
            self.ihc_name = ""
            self.ihc_note = ""
            self.ihc_position = ""

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add callback for ihc changes."""
        self.ihc.ihc_controller.add_notify_event(
            self.ihc_id, self.on_ihc_change, True)

    @property
    def should_poll(self) -> bool:
        """No polling needed for ihc devices."""
        return False

    def on_ihc_change(self, ihc_id, value):
        """Callback when ihc resource changes.

        Derived classes can overwrite this todo device specific stuff.
        """
        raise NotImplementedError

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if not self.ihc.info:
            return {}
        return {
            'ihc_id': self.ihc_id,
            'ihc_name': self.ihc_name,
            'ihc_note': self.ihc_note,
            'ihc_position': self.ihc_position
        }
