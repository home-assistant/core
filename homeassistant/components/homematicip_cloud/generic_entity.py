"""Generic entity for the HomematicIP Cloud component."""
from __future__ import annotations

import logging
from typing import Any

from homematicip.aio.device import AsyncDevice
from homematicip.aio.group import AsyncGroup

from homeassistant.const import ATTR_ID
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN as HMIPC_DOMAIN
from .hap import AsyncHome, HomematicipHAP

_LOGGER = logging.getLogger(__name__)

ATTR_MODEL_TYPE = "model_type"
ATTR_LOW_BATTERY = "low_battery"
ATTR_CONFIG_PENDING = "config_pending"
ATTR_CONNECTION_TYPE = "connection_type"
ATTR_DUTY_CYCLE_REACHED = "duty_cycle_reached"
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
ATTR_EVENT_DELAY = "event_delay"

DEVICE_ATTRIBUTE_ICONS = {
    "lowBat": "mdi:battery-outline",
    "sabotage": "mdi:shield-alert",
    "dutyCycle": "mdi:alert",
    "deviceOverheated": "mdi:alert",
    "deviceOverloaded": "mdi:alert",
    "deviceUndervoltage": "mdi:alert",
    "configPending": "mdi:alert-circle",
}

DEVICE_ATTRIBUTES = {
    "modelType": ATTR_MODEL_TYPE,
    "connectionType": ATTR_CONNECTION_TYPE,
    "sabotage": ATTR_SABOTAGE,
    "dutyCycle": ATTR_DUTY_CYCLE_REACHED,
    "rssiDeviceValue": ATTR_RSSI_DEVICE,
    "rssiPeerValue": ATTR_RSSI_PEER,
    "deviceOverheated": ATTR_DEVICE_OVERHEATED,
    "deviceOverloaded": ATTR_DEVICE_OVERLOADED,
    "deviceUndervoltage": ATTR_DEVICE_UNTERVOLTAGE,
    "configPending": ATTR_CONFIG_PENDING,
    "eventDelay": ATTR_EVENT_DELAY,
    "id": ATTR_ID,
}

GROUP_ATTRIBUTES = {
    "modelType": ATTR_MODEL_TYPE,
    "lowBat": ATTR_LOW_BATTERY,
    "sabotage": ATTR_SABOTAGE,
    "dutyCycle": ATTR_DUTY_CYCLE_REACHED,
    "configPending": ATTR_CONFIG_PENDING,
    "unreach": ATTR_GROUP_MEMBER_UNREACHABLE,
}


class HomematicipGenericEntity(Entity):
    """Representation of the HomematicIP generic entity."""

    def __init__(
        self,
        hap: HomematicipHAP,
        device,
        post: str | None = None,
        channel: int | None = None,
        is_multi_channel: bool | None = False,
    ) -> None:
        """Initialize the generic entity."""
        self._hap = hap
        self._home: AsyncHome = hap.home
        self._device = device
        self._post = post
        self._channel = channel
        self._is_multi_channel = is_multi_channel
        # Marker showing that the HmIP device hase been removed.
        self.hmip_device_removed = False
        _LOGGER.info("Setting up %s (%s)", self.name, self._device.modelType)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        # Only physical devices should be HA devices.
        if isinstance(self._device, AsyncDevice):
            return DeviceInfo(
                identifiers={
                    # Serial numbers of Homematic IP device
                    (HMIPC_DOMAIN, self._device.id)
                },
                manufacturer=self._device.oem,
                model=self._device.modelType,
                name=self._device.label,
                sw_version=self._device.firmwareVersion,
                # Link to the homematic ip access point.
                via_device=(HMIPC_DOMAIN, self._device.homeId),
            )
        return None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._hap.hmip_device_by_entity_id[self.entity_id] = self._device
        self._device.on_update(self._async_device_changed)
        self._device.on_remove(self._async_device_removed)

    @callback
    def _async_device_changed(self, *args, **kwargs) -> None:
        """Handle device state changes."""
        # Don't update disabled entities
        if self.enabled:
            _LOGGER.debug("Event %s (%s)", self.name, self._device.modelType)
            self.async_write_ha_state()
        else:
            _LOGGER.debug(
                "Device Changed Event for %s (%s) not fired. Entity is disabled",
                self.name,
                self._device.modelType,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when hmip device will be removed from hass."""

        # Only go further if the device/entity should be removed from registries
        # due to a removal of the HmIP device.

        if self.hmip_device_removed:
            try:
                del self._hap.hmip_device_by_entity_id[self.entity_id]
                self.async_remove_from_registries()
            except KeyError as err:
                _LOGGER.debug("Error removing HMIP device from registry: %s", err)

    @callback
    def async_remove_from_registries(self) -> None:
        """Remove entity/device from registry."""
        # Remove callback from device.
        self._device.remove_callback(self._async_device_changed)
        self._device.remove_callback(self._async_device_removed)

        if not self.registry_entry:
            return

        if device_id := self.registry_entry.device_id:
            # Remove from device registry.
            device_registry = dr.async_get(self.hass)
            if device_id in device_registry.devices:
                # This will also remove associated entities from entity registry.
                device_registry.async_remove_device(device_id)
        else:
            # Remove from entity registry.
            # Only relevant for entities that do not belong to a device.
            if entity_id := self.registry_entry.entity_id:
                entity_registry = er.async_get(self.hass)
                if entity_id in entity_registry.entities:
                    entity_registry.async_remove(entity_id)

    @callback
    def _async_device_removed(self, *args, **kwargs) -> None:
        """Handle hmip device removal."""
        # Set marker showing that the HmIP device hase been removed.
        self.hmip_device_removed = True
        self.hass.async_create_task(self.async_remove(force_remove=True))

    @property
    def name(self) -> str:
        """Return the name of the generic entity."""

        name = None
        # Try to get a label from a channel.
        if hasattr(self._device, "functionalChannels"):
            if self._is_multi_channel:
                name = self._device.functionalChannels[self._channel].label
            else:
                if len(self._device.functionalChannels) > 1:
                    name = self._device.functionalChannels[1].label

        # Use device label, if name is not defined by channel label.
        if not name:
            name = self._device.label
            if self._post:
                name = f"{name} {self._post}"
            elif self._is_multi_channel:
                name = f"{name} Channel{self._channel}"

        # Add a prefix to the name if the homematic ip home has a name.
        if name and self._home.name:
            name = f"{self._home.name} {name}"

        return name

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return not self._device.unreach

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        unique_id = f"{self.__class__.__name__}_{self._device.id}"
        if self._is_multi_channel:
            unique_id = (
                f"{self.__class__.__name__}_Channel{self._channel}_{self._device.id}"
            )

        return unique_id

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        for attr, icon in DEVICE_ATTRIBUTE_ICONS.items():
            if getattr(self._device, attr, None):
                return icon

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the generic entity."""
        state_attr = {}

        if isinstance(self._device, AsyncDevice):
            for attr, attr_key in DEVICE_ATTRIBUTES.items():
                if attr_value := getattr(self._device, attr, None):
                    state_attr[attr_key] = attr_value

            state_attr[ATTR_IS_GROUP] = False

        if isinstance(self._device, AsyncGroup):
            for attr, attr_key in GROUP_ATTRIBUTES.items():
                if attr_value := getattr(self._device, attr, None):
                    state_attr[attr_key] = attr_value

            state_attr[ATTR_IS_GROUP] = True

        return state_attr
