"""Support for HDMI CEC."""

from __future__ import annotations

from homeassistant.helpers.entity import Entity

from .const import DOMAIN, EVENT_HDMI_CEC_UNAVAILABLE

ATTR_PHYSICAL_ADDRESS = "physical_address"
ATTR_TYPE = "type"
ATTR_TYPE_ID = "type_id"
ATTR_VENDOR_NAME = "vendor_name"
ATTR_VENDOR_ID = "vendor_id"

ICON_UNKNOWN = "mdi:help"
ICON_AUDIO = "mdi:speaker"
ICON_PLAYER = "mdi:play"
ICON_TUNER = "mdi:radio"
ICON_RECORDER = "mdi:microphone"
ICON_TV = "mdi:television"
ICONS_BY_TYPE = {
    0: ICON_TV,
    1: ICON_RECORDER,
    3: ICON_TUNER,
    4: ICON_PLAYER,
    5: ICON_AUDIO,
}


class CecEntity(Entity):
    """Representation of a HDMI CEC device entity."""

    _attr_should_poll = False

    def __init__(self, device, logical) -> None:
        """Initialize the device."""
        self._device = device
        self._logical_address = logical
        self.entity_id = f"{DOMAIN}.{self._logical_address}"
        self._set_attr_name()
        self._attr_icon = ICONS_BY_TYPE.get(self._device.type, ICON_UNKNOWN)

    def _set_attr_name(self):
        """Set name."""
        if (
            self._device.osd_name is not None
            and self.vendor_name is not None
            and self.vendor_name != "Unknown"
        ):
            self._attr_name = f"{self.vendor_name} {self._device.osd_name}"
        elif self._device.osd_name is None:
            self._attr_name = f"{self._device.type_name} {self._logical_address}"
        else:
            self._attr_name = f"{self._device.type_name} {self._logical_address} ({self._device.osd_name})"

    def _hdmi_cec_unavailable(self, callback_event):
        self._attr_available = False
        self.schedule_update_ha_state(False)

    async def async_added_to_hass(self):
        """Register HDMI callbacks after initialization."""
        self._device.set_update_callback(self._update)
        self.hass.bus.async_listen(
            EVENT_HDMI_CEC_UNAVAILABLE, self._hdmi_cec_unavailable
        )

    def _update(self, device=None):
        """Device status changed, schedule an update."""
        self._attr_available = True
        self.schedule_update_ha_state(True)

    @property
    def vendor_id(self):
        """Return the ID of the device's vendor."""
        return self._device.vendor_id

    @property
    def vendor_name(self):
        """Return the name of the device's vendor."""
        return self._device.vendor

    @property
    def physical_address(self):
        """Return the physical address of device in HDMI network."""
        return str(self._device.physical_address)

    @property
    def type(self):
        """Return a string representation of the device's type."""
        return self._device.type_name

    @property
    def type_id(self):
        """Return the type ID of device."""
        return self._device.type

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        state_attr = {}
        if self.vendor_id is not None:
            state_attr[ATTR_VENDOR_ID] = self.vendor_id
            state_attr[ATTR_VENDOR_NAME] = self.vendor_name
        if self.type_id is not None:
            state_attr[ATTR_TYPE_ID] = self.type_id
            state_attr[ATTR_TYPE] = self.type
        if self.physical_address is not None:
            state_attr[ATTR_PHYSICAL_ADDRESS] = self.physical_address
        return state_attr
