"""Number platform for Webex CE devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WebexCEConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming device
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebexCEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Webex CE number entities."""
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

    # Add number control
    async_add_entities(
        [
            WebexCEVolumeNumber(client, device_info_dict),
        ]
    )


class WebexCEVolumeNumber(NumberEntity):
    """Representation of a Webex CE volume control."""

    _attr_has_entity_name = True
    _attr_translation_key = "volume"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the number entity."""
        self._client = client
        self._attr_device_info = device_info
        # Extract serial from device info identifiers
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_volume"
        self._attr_native_value = None
        self._attr_icon = "mdi:volume-high"

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()

        # Subscribe to volume status updates
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "Audio", "Volume"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        _LOGGER.debug("Received volume feedback for %s: %s", self.unique_id, params)

        # The params dict contains the status path and value
        # For Status/Audio/Volume, navigate to the value
        try:
            volume_data = params.get("Status", {}).get("Audio", {}).get("Volume")
            # Volume can be an integer directly or in a nested structure
            if isinstance(volume_data, dict):
                # Try common keys for volume value
                volume = volume_data.get("value") or volume_data.get("Value")
            else:
                volume = volume_data

            if volume is not None:
                volume = int(volume)
                self._attr_native_value = volume

                # Update icon based on volume level
                if volume == 0:
                    self._attr_icon = "mdi:volume-off"
                elif volume < 33:
                    self._attr_icon = "mdi:volume-low"
                elif volume < 67:
                    self._attr_icon = "mdi:volume-medium"
                else:
                    self._attr_icon = "mdi:volume-high"

                self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.warning("Unexpected volume feedback format: %s - %s", params, err)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_set_native_value(self, value: float) -> None:
        """Set the volume level."""
        volume = int(value)
        _LOGGER.debug("Setting volume to: %s", volume)

        try:
            # Execute xCommand Audio Volume Set with Level parameter
            await self._client.xcommand(["Audio", "Volume", "Set"], Level=volume)

            # Optimistically update the state
            self._attr_native_value = volume

            # Update icon based on volume level
            if volume == 0:
                self._attr_icon = "mdi:volume-off"
            elif volume < 33:
                self._attr_icon = "mdi:volume-low"
            elif volume < 67:
                self._attr_icon = "mdi:volume-medium"
            else:
                self._attr_icon = "mdi:volume-high"

            self.async_write_ha_state()
        except Exception:
            _LOGGER.exception("Failed to set volume to %s", volume)
            raise


class WebexCEBrightnessNumber(NumberEntity):
    """Representation of touch panel brightness control."""

    _attr_has_entity_name = True
    _attr_translation_key = "touch_panel_brightness"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the number entity."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_touch_panel_brightness"
        self._attr_native_value = None
        self._attr_icon = "mdi:brightness-6"

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Configuration", "UserInterface", "TouchPanel", "Brightness"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        _LOGGER.debug("Received brightness feedback for %s: %s", self.unique_id, params)
        try:
            brightness_data = (
                params.get("Configuration", {})
                .get("UserInterface", {})
                .get("TouchPanel", {})
                .get("Brightness")
            )
            if brightness_data is not None:
                brightness = int(brightness_data)
                self._attr_native_value = brightness
                self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.warning("Unexpected brightness feedback: %s - %s", params, err)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_set_native_value(self, value: float) -> None:
        """Set the brightness level."""
        brightness = int(value)
        _LOGGER.debug("Setting brightness to: %s", brightness)
        try:
            await self._client.xcommand(
                ["Configuration", "UserInterface", "TouchPanel", "Brightness", "Set"],
                Value=brightness,
            )
            self._attr_native_value = brightness
            self.async_write_ha_state()
        except Exception:
            _LOGGER.exception("Failed to set brightness to %s", brightness)
            raise
