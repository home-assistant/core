"""Generic device for the HomematicIP Cloud component."""
import logging

from homeassistant.components import homematicip_cloud
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_LOW_BATTERY = 'low_battery'
ATTR_MODEL_TYPE = 'model_type'
# RSSI HAP -> Device
ATTR_RSSI_DEVICE = 'rssi_device'
# RSSI Device -> HAP
ATTR_RSSI_PEER = 'rssi_peer'
ATTR_SABOTAGE = 'sabotage'
ATTR_GROUP_MEMBER_UNREACHABLE = 'group_member_unreachable'


class HomematicipGenericDevice(Entity):
    """Representation of an HomematicIP generic device."""

    def __init__(self, home, device, post=None):
        """Initialize the generic device."""
        self._home = home
        self._device = device
        self.post = post
        _LOGGER.info("Setting up %s (%s)", self.name, self._device.modelType)

    @property
    def device_info(self):
        """Return device specific attributes."""
        from homematicip.aio.device import AsyncDevice
        # Only physical devices should be HA devices.
        if isinstance(self._device, AsyncDevice):
            return {
                'identifiers': {
                    # Serial numbers of Homematic IP device
                    (homematicip_cloud.DOMAIN, self._device.id)
                },
                'name': self._device.label,
                'manufacturer': self._device.oem,
                'model': self._device.modelType,
                'sw_version': self._device.firmwareVersion,
                'via_hub': (homematicip_cloud.DOMAIN, self._device.homeId),
            }
        return None

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._device.on_update(self._device_changed)

    def _device_changed(self, *args, **kwargs):
        """Handle device state changes."""
        _LOGGER.debug("Event %s (%s)", self.name, self._device.modelType)
        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the generic device."""
        name = self._device.label
        if self._home.name is not None and self._home.name != '':
            name = "{} {}".format(self._home.name, name)
        if self.post is not None and self.post != '':
            name = "{} {}".format(name, self.post)
        return name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def available(self):
        """Device available."""
        return not self._device.unreach

    @property
    def unique_id(self):
        """Return a unique ID."""
        return "{}_{}".format(self.__class__.__name__, self._device.id)

    @property
    def icon(self):
        """Return the icon."""
        if hasattr(self._device, 'lowBat') and self._device.lowBat:
            return 'mdi:battery-outline'
        if hasattr(self._device, 'sabotage') and self._device.sabotage:
            return 'mdi:alert'
        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the generic device."""
        attr = {ATTR_MODEL_TYPE: self._device.modelType}
        if hasattr(self._device, 'lowBat') and self._device.lowBat:
            attr[ATTR_LOW_BATTERY] = self._device.lowBat
        if hasattr(self._device, 'sabotage') and self._device.sabotage:
            attr[ATTR_SABOTAGE] = self._device.sabotage
        if hasattr(self._device, 'rssiDeviceValue') and \
                self._device.rssiDeviceValue:
            attr[ATTR_RSSI_DEVICE] = self._device.rssiDeviceValue
        if hasattr(self._device, 'rssiPeerValue') and \
                self._device.rssiPeerValue:
            attr[ATTR_RSSI_PEER] = self._device.rssiPeerValue
        return attr
