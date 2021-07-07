"""Base class for a device entity integrated in devolo Home Control."""
from __future__ import annotations

import logging

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.homecontrol import HomeControl

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN
from .subscriber import Subscriber

_LOGGER = logging.getLogger(__name__)


class DevoloDeviceEntity(Entity):
    """Abstract representation of a device within devolo Home Control."""

    def __init__(
        self, homecontrol: HomeControl, device_instance: Zwave, element_uid: str
    ) -> None:
        """Initialize a devolo device entity."""
        self._device_instance = device_instance
        self._unique_id = element_uid
        self._homecontrol = homecontrol
        self._name: str = device_instance.settings_property[
            "general_device_settings"
        ].name
        self._area = device_instance.settings_property["general_device_settings"].zone
        self._device_class: str | None = None
        self._value: int
        self._unit = ""
        self._enabled_default = True

        # This is not doing I/O. It fetches an internal state of the API
        self._available: bool = device_instance.is_online()

        # Get the brand and model information
        self._brand = device_instance.brand
        self._model = device_instance.name

        self.subscriber: Subscriber | None = None
        self.sync_callback = self._sync

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self.subscriber = Subscriber(self._name, callback=self.sync_callback)
        self._homecontrol.publisher.register(
            self._device_instance.uid, self.subscriber, self.sync_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity is removed or disabled."""
        self._homecontrol.publisher.unregister(
            self._device_instance.uid, self.subscriber
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the entity."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._device_instance.uid)},
            "name": self._name,
            "manufacturer": self._brand,
            "model": self._model,
            "suggested_area": self._area,
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def should_poll(self) -> bool:
        """Return the polling state."""
        return False

    @property
    def name(self) -> str:
        """Return the display name of this entity."""
        return self._name

    @property
    def available(self) -> bool:
        """Return the online state."""
        return self._available

    def _sync(self, message: tuple) -> None:
        """Update the state."""
        if message[0] == self._unique_id:
            self._value = message[1]
        else:
            self._generic_message(message)
        self.schedule_update_ha_state()

    def _generic_message(self, message: tuple) -> None:
        """Handle generic messages."""
        if len(message) == 3 and message[2] == "battery_level":
            self._value = message[1]
        elif len(message) == 3 and message[2] == "status":
            # Maybe the API wants to tell us, that the device went on- or offline.
            self._available = self._device_instance.is_online()
        else:
            _LOGGER.debug("No valid message received: %s", message)
