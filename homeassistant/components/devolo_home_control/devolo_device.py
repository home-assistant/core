"""Base class for a device entity integrated in devolo Home Control."""
import logging

from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .subscriber import Subscriber

_LOGGER = logging.getLogger(__name__)

ATTR_BATTERY_LEVEL = "battery_level"


class DevoloDeviceEntity(Entity):
    """Representation of a sensor within devolo Home Control."""

    def __init__(self, homecontrol, device_instance, element_uid, name, sync):
        """Initialize a devolo device entity."""
        self._device_instance = device_instance
        self._name = name
        self._unique_id = element_uid
        self._homecontrol = homecontrol
        self._available = device_instance.is_online()

        # Get the brand and model information
        self._brand = device_instance.brand
        self._model = device_instance.name

        self._state_attrs = {}
        if hasattr(self._device_instance, "batteryLevel"):
            self._state_attrs = {ATTR_BATTERY_LEVEL: self._device_instance.batteryLevel}

        self.subscriber = None
        self.sync_callback = sync

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self.subscriber = Subscriber(
            self._device_instance.itemName, callback=self.sync_callback
        )
        self._homecontrol.publisher.register(
            self._device_instance.uid, self.subscriber, self.sync_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity is removed or disabled."""
        self._homecontrol.publisher.unregister(
            self._device_instance.uid, self.subscriber
        )

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._device_instance.uid)},
            "name": self._device_instance.itemName,
            "manufacturer": self._brand,
            "model": self._model,
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the display name of this entity."""
        return self._name

    @property
    def available(self) -> bool:
        """Return the online state."""
        return self._available
