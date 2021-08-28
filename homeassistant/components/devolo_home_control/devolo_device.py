"""Base class for a device entity integrated in devolo Home Control."""
from __future__ import annotations

import logging

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.homecontrol import HomeControl

from homeassistant.helpers.entity import Entity

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
        self._homecontrol = homecontrol

        self._attr_available = (
            device_instance.is_online()
        )  # This is not doing I/O. It fetches an internal state of the API
        self._attr_name: str = device_instance.settings_property[
            "general_device_settings"
        ].name
        self._attr_should_poll = False
        self._attr_unique_id = element_uid
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._device_instance.uid)},
            "name": self._attr_name,
            "manufacturer": device_instance.brand,
            "model": device_instance.name,
            "suggested_area": device_instance.settings_property[
                "general_device_settings"
            ].zone,
        }

        self.subscriber: Subscriber | None = None
        self.sync_callback = self._sync
        self._value: int

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self.subscriber = Subscriber(self._attr_name, callback=self.sync_callback)
        self._homecontrol.publisher.register(
            self._device_instance.uid, self.subscriber, self.sync_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity is removed or disabled."""
        self._homecontrol.publisher.unregister(
            self._device_instance.uid, self.subscriber
        )

    def _sync(self, message: tuple) -> None:
        """Update the state."""
        if message[0] == self._attr_unique_id:
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
            self._attr_available = self._device_instance.is_online()
        else:
            _LOGGER.debug("No valid message received: %s", message)
