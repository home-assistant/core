"""Implements a base class for all IHC devices."""
import asyncio
from xml.etree.ElementTree import Element

from homeassistant.helpers.entity import Entity


class IHCDevice(Entity):
    """Base class for all ihc devices.

    All IHC devices have an associated IHC resource. IHCDevice handled the
    registration of the IHC controller callback when the IHC resource changes.
    Derived classes must implement the on_ihc_change method
    """

    def __init__(self, ihc_controller, name, ihc_id: int, info: bool,
                 product: Element=None):
        """Initialize IHC attributes."""
        self.ihc_controller = ihc_controller
        self._name = name
        self.ihc_id = ihc_id
        self.info = info
        if product:
            self.ihc_name = product.attrib['name']
            self.ihc_note = product.attrib['note']
            self.ihc_position = product.attrib['position']
        else:
            self.ihc_name = ''
            self.ihc_note = ''
            self.ihc_position = ''

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add callback for ihc changes."""
        self.ihc_controller.add_notify_event(
            self.ihc_id, self.on_ihc_change, True)

    @property
    def should_poll(self) -> bool:
        """No polling needed for ihc devices."""
        return False

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if not self.info:
            return {}
        return {
            'ihc_id': self.ihc_id,
            'ihc_name': self.ihc_name,
            'ihc_note': self.ihc_note,
            'ihc_position': self.ihc_position
        }

    def on_ihc_change(self, ihc_id, value):
        """Callback when ihc resource changes.

        Derived classes must overwrite this to do device specific stuff.
        """
        raise NotImplementedError
