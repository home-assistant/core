"""Generic entity for the HomematicIP Cloud component."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from homematicip.base.functionalChannels import FunctionalChannel
from homematicip.device import Device
from homematicip.group import Group

from homeassistant.const import ATTR_ID
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
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

    _attr_should_poll = False

    def __init__(
        self,
        hap: HomematicipHAP,
        device,
        post: str | None = None,
        channel: int | None = None,
        is_multi_channel: bool | None = False,
        channel_real_index: int | None = None,
    ) -> None:
        """Initialize the generic entity."""
        self._hap = hap
        self._home: AsyncHome = hap.home
        self._device = device
        self._post = post
        self._channel = channel

        # channel_real_index represents the actual index of the devices channel.
        # Accessing a functionalChannel by the channel parameter or array index is unreliable,
        # because the functionalChannels array is sorted as strings, not numbers.
        # For example, channels are ordered as: 1, 10, 11, 12, 2, 3, ...
        # Using channel_real_index ensures you reference the correct channel.
        self._channel_real_index: int | None = channel_real_index

        self._is_multi_channel = is_multi_channel
        self.functional_channel = None
        with contextlib.suppress(ValueError):
            self.functional_channel = self.get_current_channel()

        # Marker showing that the HmIP device hase been removed.
        self.hmip_device_removed = False

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        # Only physical devices should be HA devices.
        if isinstance(self._device, Device):
            device_id = str(self._device.id)
            home_id = str(self._device.homeId)

            return DeviceInfo(
                identifiers={
                    # Serial numbers of Homematic IP device
                    (DOMAIN, device_id)
                },
                manufacturer=self._device.oem,
                model=self._device.modelType,
                name=self._device.label,
                sw_version=self._device.firmwareVersion,
                # Link to the homematic ip access point.
                via_device=(DOMAIN, home_id),
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
        else:  # noqa: PLR5501
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
        self.hass.async_create_task(
            self.async_remove(force_remove=True), eager_start=False
        )

    @property
    def name(self) -> str:
        """Return the name of the generic entity."""

        name = ""
        # Try to get a label from a channel.
        functional_channels = getattr(self._device, "functionalChannels", None)
        if functional_channels and self.functional_channel:
            if self._is_multi_channel:
                label = getattr(self.functional_channel, "label", None)
                if label:
                    name = str(label)
            elif len(functional_channels) > 1:
                label = getattr(functional_channels[1], "label", None)
                if label:
                    name = str(label)

        # Use device label, if name is not defined by channel label.
        if not name:
            name = self._device.label or ""
            if self._post:
                name = f"{name} {self._post}"
            elif self._is_multi_channel:
                name = f"{name} Channel{self.get_channel_index()}"

        # Add a prefix to the name if the homematic ip home has a name.
        home_name = getattr(self._home, "name", None)
        if name and home_name:
            name = f"{home_name} {name}"

        return name

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return not self._device.unreach

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        unique_id = f"{self.__class__.__name__}_{self._device.id}"
        if self._is_multi_channel:
            unique_id = f"{self.__class__.__name__}_Channel{self.get_channel_index()}_{self._device.id}"

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

        if isinstance(self._device, Device):
            for attr, attr_key in DEVICE_ATTRIBUTES.items():
                if attr_value := getattr(self._device, attr, None):
                    state_attr[attr_key] = attr_value

            state_attr[ATTR_IS_GROUP] = False

        if isinstance(self._device, Group):
            for attr, attr_key in GROUP_ATTRIBUTES.items():
                if attr_value := getattr(self._device, attr, None):
                    state_attr[attr_key] = attr_value

            state_attr[ATTR_IS_GROUP] = True

        return state_attr

    def get_current_channel(self) -> FunctionalChannel:
        """Return the FunctionalChannel for the device.

        Resolution priority:
        1. For multi-channel entities with a real index, find channel by index match.
        2. For multi-channel entities without a real index, use the provided channel position.
        3. For non multi-channel entities with >1 channels, use channel at position 1
           (index 0 is often a meta/service channel in HmIP).
        Raises ValueError if no suitable channel can be resolved.
        """
        functional_channels = getattr(self._device, "functionalChannels", None)
        if not functional_channels:
            raise ValueError(
                f"Device {getattr(self._device, 'id', 'unknown')} has no functionalChannels"
            )

        # Multi-channel handling
        if self._is_multi_channel:
            # Prefer real index mapping when provided to avoid ordering issues.
            if self._channel_real_index is not None:
                for channel in functional_channels:
                    if channel.index == self._channel_real_index:
                        return channel
                raise ValueError(
                    f"Real channel index {self._channel_real_index} not found for device "
                    f"{getattr(self._device, 'id', 'unknown')}"
                )
            # Fallback: positional channel (already sorted as strings upstream).
            if self._channel is not None and 0 <= self._channel < len(
                functional_channels
            ):
                return functional_channels[self._channel]
            raise ValueError(
                f"Channel position {self._channel} invalid for device "
                f"{getattr(self._device, 'id', 'unknown')} (len={len(functional_channels)})"
            )

        # Single-channel / non multi-channel entity: choose second element if available
        if len(functional_channels) > 1:
            return functional_channels[1]
        return functional_channels[0]

    def get_channel_index(self) -> int:
        """Return the correct channel index for this entity.

        Prefers channel_real_index if set, otherwise returns channel.
        This ensures the correct channel is used even if the functionalChannels list is not numerically ordered.
        """
        if self._channel_real_index is not None:
            return self._channel_real_index

        if self._channel is not None:
            return self._channel

        return 1

    def get_channel_or_raise(self) -> FunctionalChannel:
        """Return the FunctionalChannel or raise an error if not found."""
        if not self.functional_channel:
            raise ValueError(
                f"No functional channel found for device {getattr(self._device, 'id', 'unknown')}"
            )
        return self.functional_channel
