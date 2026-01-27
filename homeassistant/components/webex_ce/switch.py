"""Switch platform for Webex CE devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up Webex CE switch entities."""
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

    # Add microphone and video mute switches
    async_add_entities(
        [
            WebexCEMicrophoneMuteSwitch(client, device_info_dict),
            WebexCEVideoMuteSwitch(client, device_info_dict),
            WebexCEPresentationSwitch(client, device_info_dict),
            WebexCESelfViewSwitch(client, device_info_dict),
        ]
    )


class WebexCESelfViewSwitch(SwitchEntity):
    """Representation of a Webex CE self view switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "self_view"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the switch."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_self_view"
        self._attr_is_on = False
        self._attr_icon = "mdi:monitor-eye"

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "Video", "Selfview", "Mode"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        _LOGGER.debug("Received feedback for %s: %s", self.unique_id, params)
        try:
            mode = (
                params.get("Status", {})
                .get("Video", {})
                .get("Selfview", {})
                .get("Mode", "Off")
            )
            self._attr_is_on = mode == "On"
            self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError):
            _LOGGER.warning("Unexpected feedback format: %s", params)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on self view."""
        try:
            await self._client.xcommand(["Video", "Selfview", "Set"], Mode="On")
            self._attr_is_on = True
            self.async_write_ha_state()
        except Exception:
            _LOGGER.exception("Failed to turn on self view")
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off self view."""
        try:
            await self._client.xcommand(["Video", "Selfview", "Set"], Mode="Off")
            self._attr_is_on = False
            self.async_write_ha_state()
        except Exception:
            _LOGGER.exception("Failed to turn off self view")
            raise


class WebexCEPresentationSwitch(SwitchEntity):
    """Representation of a Webex CE presentation switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "presentation"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the switch."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_presentation"
        self._attr_is_on = False
        self._attr_icon = "mdi:presentation"

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "Conference", "Presentation", "Mode"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        _LOGGER.debug("Received feedback for %s: %s", self.unique_id, params)
        try:
            mode = (
                params.get("Status", {})
                .get("Conference", {})
                .get("Presentation", {})
                .get("Mode", "Off")
            )
            self._attr_is_on = mode in ("Sending", "Receiving", "On")
            self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError):
            _LOGGER.warning("Unexpected feedback format: %s", params)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start presentation."""
        try:
            await self._client.xcommand(["Presentation", "Start"])
            self._attr_is_on = True
            self.async_write_ha_state()
        except Exception:
            _LOGGER.exception("Failed to start presentation")
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop presentation."""
        try:
            await self._client.xcommand(["Presentation", "Stop"])
            self._attr_is_on = False
            self.async_write_ha_state()
        except Exception:
            _LOGGER.exception("Failed to stop presentation")
            raise


class WebexCEMicrophoneMuteSwitch(SwitchEntity):
    """Representation of a Webex CE microphone mute switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "microphone_mute"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the switch."""
        self._client = client
        self._attr_device_info = device_info
        # Extract serial from device info identifiers
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_microphone_mute"
        self._attr_is_on = False
        self._attr_icon = "mdi:microphone"

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()

        # Subscribe to microphone mute status updates
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "Audio", "Microphones", "Mute"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        _LOGGER.debug("Received feedback for %s: %s", self.unique_id, params)

        # The params dict contains the status path and value
        # For Status/Audio/Microphones/Mute, the value is at params['Status']['Audio']['Microphones']['Mute']
        try:
            mute_status = (
                params.get("Status", {})
                .get("Audio", {})
                .get("Microphones", {})
                .get("Mute", "Off")
            )
        except (AttributeError, KeyError, TypeError):
            _LOGGER.warning("Unexpected feedback format: %s", params)
            return

        # "On" means muted, "Off" means unmuted
        self._attr_is_on = mute_status == "On"
        self._attr_icon = "mdi:microphone-off" if self._attr_is_on else "mdi:microphone"
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Mute the microphones."""
        try:
            await self._client.xcommand(["Audio", "Microphones", "Mute"])
            self._attr_is_on = True
            self._attr_icon = "mdi:microphone-off"
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Failed to mute microphones: %s", err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unmute the microphones."""
        try:
            await self._client.xcommand(["Audio", "Microphones", "Unmute"])
            self._attr_is_on = False
            self._attr_icon = "mdi:microphone"
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Failed to unmute microphones: %s", err)
            raise


class WebexCEVideoMuteSwitch(SwitchEntity):
    """Representation of a Webex CE video mute switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "video_mute"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the switch."""
        self._client = client
        self._attr_device_info = device_info
        # Extract serial from device info identifiers
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_video_mute"
        self._attr_is_on = False
        self._attr_icon = "mdi:video"

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()

        # Subscribe to video mute status updates
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "Video", "Input", "MainVideoMute"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        _LOGGER.debug("Received feedback for %s: %s", self.unique_id, params)

        # The params dict contains the status path and value
        # For Status/Video/Input/MainVideoMute, the value is at params['Status']['Video']['Input']['MainVideoMute']
        try:
            mute_status = (
                params.get("Status", {})
                .get("Video", {})
                .get("Input", {})
                .get("MainVideoMute", "Off")
            )
        except (AttributeError, KeyError, TypeError):
            _LOGGER.warning("Unexpected feedback format: %s", params)
            return

        # "On" means muted, "Off" means unmuted
        self._attr_is_on = mute_status == "On"
        self._attr_icon = "mdi:video-off" if self._attr_is_on else "mdi:video"
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Mute the video."""
        try:
            await self._client.xcommand(["Video", "Input", "MainVideo", "Mute"])
            self._attr_is_on = True
            self._attr_icon = "mdi:video-off"
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Failed to mute video: %s", err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unmute the video."""
        try:
            await self._client.xcommand(["Video", "Input", "MainVideo", "Unmute"])
            self._attr_is_on = False
            self._attr_icon = "mdi:video"
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Failed to unmute video: %s", err)
            raise
