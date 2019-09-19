"""Generic device for the HomematicIP Cloud component."""
import logging
from typing import Optional

from homematicip.aio.device import AsyncDevice
from homematicip.aio.home import AsyncHome

from homeassistant.components import homematicip_cloud
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_MODEL_TYPE = "model_type"
ATTR_ID = "id"
ATTR_IS_GROUP = "is_group"
# RSSI HAP -> Device
ATTR_RSSI_DEVICE = "rssi_device"
# RSSI Device -> HAP
ATTR_RSSI_PEER = "rssi_peer"
ATTR_SABOTAGE = "sabotage"
ATTR_GROUP_MEMBER_UNREACHABLE = "group_member_unreachable"
ATTR_DEVICE_OVERHEATED = "device_overheated"
ATTR_DEVICE_OVERLOADED = "device_overloaded"
ATTR_DEVICE_UNTERVOLTAGE = "device_undervoltage"

DEVICE_ATTRIBUTE_ICONS = {
    "lowBat": "mdi:battery-outline",
    "sabotage": "mdi:alert",
    "deviceOverheated": "mdi:alert",
    "deviceOverloaded": "mdi:alert",
    "deviceUndervoltage": "mdi:alert",
}

DEVICE_ATTRIBUTES = {
    "modelType": ATTR_MODEL_TYPE,
    "id": ATTR_ID,
    "sabotage": ATTR_SABOTAGE,
    "rssiDeviceValue": ATTR_RSSI_DEVICE,
    "rssiPeerValue": ATTR_RSSI_PEER,
    "deviceOverheated": ATTR_DEVICE_OVERHEATED,
    "deviceOverloaded": ATTR_DEVICE_OVERLOADED,
    "deviceUndervoltage": ATTR_DEVICE_UNTERVOLTAGE,
}


class HomematicipGenericDevice(Entity):
    """Representation of an HomematicIP generic device."""

    def __init__(self, home: AsyncHome, device, post: Optional[str] = None) -> None:
        """Initialize the generic device."""
        self._home = home
        self._device = device
        self.post = post
        _LOGGER.info("Setting up %s (%s)", self.name, self._device.modelType)

    @property
    def device_info(self):
        """Return device specific attributes."""
        # Only physical devices should be HA devices.
        if isinstance(self._device, AsyncDevice):
            return {
                "identifiers": {
                    # Serial numbers of Homematic IP device
                    (homematicip_cloud.DOMAIN, self._device.id)
                },
                "name": self._device.label,
                "manufacturer": self._device.oem,
                "model": self._device.modelType,
                "sw_version": self._device.firmwareVersion,
                "via_device": (homematicip_cloud.DOMAIN, self._device.homeId),
            }
        return None

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._device.on_update(self._async_device_changed)

    def _async_device_changed(self, *args, **kwargs):
        """Handle device state changes."""
        # Don't update disabled entities
        if self.enabled:
            _LOGGER.debug("Event %s (%s)", self.name, self._device.modelType)
            self.async_schedule_update_ha_state()
        else:
            _LOGGER.debug(
                "Device Changed Event for %s (%s) not fired. Entity is disabled.",
                self.name,
                self._device.modelType,
            )

    @property
    def name(self) -> str:
        """Return the name of the generic device."""
        name = self._device.label
        if self._home.name is not None and self._home.name != "":
            name = f"{self._home.name} {name}"
        if self.post is not None and self.post != "":
            name = f"{name} {self.post}"
        return name

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def available(self) -> bool:
        """Device available."""
        return not self._device.unreach

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.__class__.__name__}_{self._device.id}"

    @property
    def icon(self) -> Optional[str]:
        """Return the icon."""
        for attr, icon in DEVICE_ATTRIBUTE_ICONS.items():
            if getattr(self._device, attr, None):
                return icon

        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the generic device."""
        state_attr = {}
        if isinstance(self._device, AsyncDevice):
            for attr, attr_key in DEVICE_ATTRIBUTES.items():
                attr_value = getattr(self._device, attr, None)
                if attr_value:
                    state_attr[attr_key] = attr_value

            state_attr[ATTR_IS_GROUP] = False

        return state_attr
