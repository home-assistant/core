"""Button platform for Webex CE devices."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WebexCEConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Buttons are user-triggered, no parallel update concerns
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebexCEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Webex CE button entities."""
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

    # Add call control buttons
    async_add_entities(
        [
            WebexCEAcceptCallButton(client, device_info_dict),
            WebexCERejectCallButton(client, device_info_dict),
            WebexCEDisconnectCallButton(client, device_info_dict),
        ]
    )


class WebexCEAcceptCallButton(ButtonEntity):
    """Button to accept incoming call."""

    _attr_has_entity_name = True
    _attr_translation_key = "accept_call"
    _attr_icon = "mdi:phone-check"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the button."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_accept_call"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_press(self) -> None:
        """Accept the incoming call."""
        await self._client.xcommand(["Call", "Accept"])


class WebexCERejectCallButton(ButtonEntity):
    """Button to reject incoming call."""

    _attr_has_entity_name = True
    _attr_translation_key = "reject_call"
    _attr_icon = "mdi:phone-cancel"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the button."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_reject_call"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_press(self) -> None:
        """Reject the incoming call."""
        await self._client.xcommand(["Call", "Reject"])


class WebexCEDisconnectCallButton(ButtonEntity):
    """Button to disconnect active call."""

    _attr_has_entity_name = True
    _attr_translation_key = "disconnect_call"
    _attr_icon = "mdi:phone-hangup"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the button."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_disconnect_call"

    async def async_press(self) -> None:
        """Disconnect the active call."""
        await self._client.xcommand(["Call", "Disconnect"])


class WebexCEHoldCallButton(ButtonEntity):
    """Button to hold active call."""

    _attr_has_entity_name = True
    _attr_translation_key = "hold_call"
    _attr_icon = "mdi:phone-paused"
    _attr_entity_registry_enabled_default = False

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the button."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_hold_call"

    async def async_press(self) -> None:
        """Hold the active call."""
        await self._client.xcommand(["Call", "Hold"])


class WebexCEResumeCallButton(ButtonEntity):
    """Button to resume held call."""

    _attr_has_entity_name = True
    _attr_translation_key = "resume_call"
    _attr_icon = "mdi:phone"
    _attr_entity_registry_enabled_default = False

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the button."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_resume_call"

    async def async_press(self) -> None:
        """Resume the held call."""
        await self._client.xcommand(["Call", "Resume"])


class WebexCEWakeupDisplayButton(ButtonEntity):
    """Button to wake up display."""

    _attr_has_entity_name = True
    _attr_translation_key = "wakeup_display"
    _attr_icon = "mdi:monitor"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the button."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_wakeup_display"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_press(self) -> None:
        """Wake up the display."""
        try:
            await self._client.xcommand(["Standby", "WakeupDisplay"])
        except Exception:
            _LOGGER.exception("Failed to wake up display")
            raise
