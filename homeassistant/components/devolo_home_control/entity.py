"""Base class for a device entity integrated in devolo Home Control."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.homecontrol import HomeControl

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .subscriber import Subscriber

_LOGGER = logging.getLogger(__name__)


class DevoloDeviceEntity(Entity):
    """Abstract representation of a device within devolo Home Control."""

    _attr_has_entity_name = True

    def __init__(
        self, homecontrol: HomeControl, device_instance: Zwave, element_uid: str
    ) -> None:
        """Initialize a devolo device entity."""
        self._device_instance = device_instance
        self._homecontrol = homecontrol

        self._attr_available = (
            device_instance.is_online()
        )  # This is not doing I/O. It fetches an internal state of the API
        self._attr_should_poll = False
        self._attr_unique_id = element_uid
        self._attr_device_info = dr.DeviceInfo(
            configuration_url=f"https://{urlparse(device_instance.href).netloc}",
            identifiers={(DOMAIN, self._device_instance.uid)},
            manufacturer=device_instance.brand,
            model=device_instance.name,
            model_id=device_instance.identifier,
            name=device_instance.settings_property["general_device_settings"].name,
            suggested_area=device_instance.settings_property[
                "general_device_settings"
            ].zone,
        )

        self.subscriber: Subscriber | None = None
        self.sync_callback = self._sync

        self._value: float

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        assert self.device_info
        assert self.device_info["name"]  # The name was set on entity creation
        self.subscriber = Subscriber(
            self.device_info["name"], callback=self.sync_callback
        )
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
        if (
            len(message) == 3
            and message[2] == "battery_level"
            and self.device_class == SensorDeviceClass.BATTERY
        ):
            self._value = message[1]
        elif len(message) == 3 and message[2] == "status":
            # Maybe the API wants to tell us, that the device went on- or offline.
            state = self._device_instance.is_online()
            if state != self.available and not state:
                _LOGGER.info(
                    "Device %s is unavailable",
                    self._device_instance.settings_property[
                        "general_device_settings"
                    ].name,
                )
            if state != self.available and state:
                _LOGGER.info(
                    "Device %s is back online",
                    self._device_instance.settings_property[
                        "general_device_settings"
                    ].name,
                )
            self._attr_available = state
        elif message[1] == "del" and self.platform.config_entry:
            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, self._device_instance.uid)}
            )
            if device:
                device_registry.async_update_device(
                    device.id,
                    remove_config_entry_id=self.platform.config_entry.entry_id,
                )
        else:
            _LOGGER.debug("No valid message received: %s", message)


class DevoloMultiLevelSwitchDeviceEntity(DevoloDeviceEntity):
    """Representation of a multi level switch device within devolo Home Control. Something like a dimmer or a thermostat."""

    _attr_name = None

    def __init__(
        self, homecontrol: HomeControl, device_instance: Zwave, element_uid: str
    ) -> None:
        """Initialize a multi level switch within devolo Home Control."""
        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
        )
        self._multi_level_switch_property = device_instance.multi_level_switch_property[
            element_uid
        ]

        self._value = self._multi_level_switch_property.value
