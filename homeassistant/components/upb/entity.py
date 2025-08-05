"""Support the UPB PIM."""

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class UpbEntity(Entity):
    """Base class for all UPB entities."""

    _attr_should_poll = False

    def __init__(self, element, unique_id, upb):
        """Initialize the base of all UPB devices."""
        self._upb = upb
        self._element = element
        element_type = "link" if element.addr.is_link else "device"
        self._unique_id = f"{unique_id}_{element_type}_{element.addr}"

    @property
    def unique_id(self):
        """Return unique id of the element."""
        return self._unique_id

    @property
    def extra_state_attributes(self):
        """Return the default attributes of the element."""
        return self._element.as_dict()

    @property
    def available(self) -> bool:
        """Is the entity available to be updated."""
        return self._upb.is_connected()

    def _element_changed(self, element, changeset):
        pass

    @callback
    def _element_callback(self, element, changeset):
        """Handle callback from an UPB element that has changed."""
        self._element_changed(element, changeset)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callback for UPB changes and update entity state."""
        self._element.add_callback(self._element_callback)
        self._element_callback(self._element, {})


class UpbAttachedEntity(UpbEntity):
    """Base class for UPB attached entities."""

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for the entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._element.index)},
            manufacturer=self._element.manufacturer,
            model=self._element.product,
            name=self._element.name,
            sw_version=self._element.version,
        )
