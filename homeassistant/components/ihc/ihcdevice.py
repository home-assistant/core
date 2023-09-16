"""Implementation of a base class for all IHC devices."""
import logging

from ihcsdk.ihccontroller import IHCController

from homeassistant.helpers.entity import Entity

from .const import CONF_INFO, DOMAIN

_LOGGER = logging.getLogger(__name__)


class IHCDevice(Entity):
    """Base class for all IHC devices.

    All IHC devices have an associated IHC resource. IHCDevice handled the
    registration of the IHC controller callback when the IHC resource changes.
    Derived classes must implement the on_ihc_change method
    """

    _attr_should_poll = False

    def __init__(
        self,
        ihc_controller: IHCController,
        controller_id: str,
        name: str,
        ihc_id: int,
        product=None,
    ) -> None:
        """Initialize IHC attributes."""
        self.ihc_controller = ihc_controller
        self._name = name
        self.ihc_id = ihc_id
        self.controller_id = controller_id
        self.device_id = None
        self.suggested_area = None
        if product:
            self.ihc_name = product["name"]
            self.ihc_note = product["note"]
            self.ihc_position = product["position"]
            self.suggested_area = product["group"] if "group" in product else None
            if "id" in product:
                product_id = product["id"]
                self.device_id = f"{controller_id}_{product_id }"
                # this will name the device the same way as the IHC visual application: Product name + position
                self.device_name = product["name"]
                if self.ihc_position:
                    self.device_name += f" ({self.ihc_position})"
                self.device_model = product["model"]
        else:
            self.ihc_name = ""
            self.ihc_note = ""
            self.ihc_position = ""

    async def async_added_to_hass(self):
        """Add callback for IHC changes."""
        _LOGGER.debug("Adding IHC entity notify event: %s", self.ihc_id)
        self.ihc_controller.add_notify_event(self.ihc_id, self.on_ihc_change, True)

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self.controller_id}-{self.ihc_id}"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not self.hass.data[DOMAIN][self.controller_id][CONF_INFO]:
            return {}
        attributes = {
            "ihc_id": self.ihc_id,
            "ihc_name": self.ihc_name,
            "ihc_note": self.ihc_note,
            "ihc_position": self.ihc_position,
        }
        if len(self.hass.data[DOMAIN]) > 1:
            # We only want to show the controller id if we have more than one
            attributes["ihc_controller"] = self.controller_id
        return attributes

    def on_ihc_change(self, ihc_id, value):
        """Handle IHC resource change.

        Derived classes must overwrite this to do device specific stuff.
        """
        raise NotImplementedError
