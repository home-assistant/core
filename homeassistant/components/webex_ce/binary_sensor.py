"""Binary sensor platform for Webex CE devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WebexCEConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebexCEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Webex CE binary sensor entities."""
    client = entry.runtime_data

    # Get device info for device registry
    device_info = await client.get_device_info()

    # Create device info dict
    device_info_dict = DeviceInfo(
        identifiers={(DOMAIN, device_info["serial"])},
        name=entry.title,
        manufacturer="Cisco",
        model=device_info["product"],
        sw_version=device_info["software_version"],
    )

    # Add binary sensors for streaming only
    async_add_entities(
        [
            WebexCEStreamingStatusSensor(client, device_info_dict),
        ]
    )


class WebexCERecordingStatusSensor(BinarySensorEntity):
    """Representation of recording status."""

    _attr_has_entity_name = True
    _attr_translation_key = "recording_status"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_recording_status"
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "Recording", "Status"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        try:
            status = params.get("Status", {}).get("Recording", {}).get("Status", "Idle")
            self._attr_is_on = status in ("Recording", "Active")
            self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError) as err:
            _LOGGER.warning(
                "Unexpected recording status feedback: %s - %s", params, err
            )


class WebexCEStreamingStatusSensor(BinarySensorEntity):
    """Representation of streaming status."""

    _attr_has_entity_name = True
    _attr_translation_key = "streaming_status"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_streaming_status"
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "Streaming", "Status"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        try:
            status = (
                params.get("Status", {}).get("Streaming", {}).get("Status", "Inactive")
            )
            self._attr_is_on = status in ("Streaming", "Active")
            self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError) as err:
            _LOGGER.warning(
                "Unexpected streaming status feedback: %s - %s", params, err
            )


class WebexCEAvailabilityStatusSensor(BinarySensorEntity):
    """Representation of room availability status."""

    _attr_has_entity_name = True
    _attr_translation_key = "availability_status"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_availability_status"
        self._attr_is_on = True  # True = Free, False = Busy

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "Bookings", "Availability", "Status"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        try:
            status = (
                params.get("Status", {})
                .get("Bookings", {})
                .get("Availability", {})
                .get("Status", "Free")
            )
            self._attr_is_on = status == "Free"
            self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError) as err:
            _LOGGER.warning("Unexpected availability feedback: %s - %s", params, err)


class WebexCEEngagementProximitySensor(BinarySensorEntity):
    """Representation of engagement close proximity detection."""

    _attr_has_entity_name = True
    _attr_translation_key = "engagement_close_proximity"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_engagement_close_proximity"
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "RoomAnalytics", "Engagement", "CloseProximity"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        try:
            proximity = (
                params.get("Status", {})
                .get("RoomAnalytics", {})
                .get("Engagement", {})
                .get("CloseProximity", "False")
            )
            self._attr_is_on = proximity in ("True", True, "true")
            self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError) as err:
            _LOGGER.warning("Unexpected proximity feedback: %s - %s", params, err)
