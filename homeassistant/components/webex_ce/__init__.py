"""The Webex devices integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError

from .client import WebexCEClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type WebexCEConfigEntry = ConfigEntry[WebexCEClient]


async def async_setup_entry(hass: HomeAssistant, entry: WebexCEConfigEntry) -> bool:
    """Set up Webex devices from a config entry."""
    client = WebexCEClient(
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    try:
        await client.connect()
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to {entry.data[CONF_HOST]}"
        ) from err

    entry.runtime_data = client

    # Register services
    await async_setup_services(hass, entry)

    # Setup UI extension event handling
    async def handle_ui_event(event_data: dict) -> None:
        """Handle UI extension button press events."""
        hass.bus.fire(
            f"{DOMAIN}_ui_event",
            {
                "device_id": entry.entry_id,
                "widget_id": event_data.get("WidgetId"),
                "type": event_data.get("Type"),
                "value": event_data.get("Value"),
            },
        )

    # UI event handling disabled - xows library doesn't support subscribe_event
    # try:
    #     await client.subscribe_ui_events(handle_ui_event)
    # except Exception as err:
    #     _LOGGER.warning("Failed to subscribe to UI events: %s", err)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WebexCEConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.disconnect()

    return unload_ok


async def _create_dial_service(entry: WebexCEConfigEntry) -> Callable:
    """Create dial service handler."""

    async def dial_service(call: ServiceCall) -> None:
        """Dial a number or SIP URI."""
        client = entry.runtime_data
        number = call.data["number"]
        try:
            await client.xcommand(["Dial"], Number=number)
        except Exception as err:
            raise HomeAssistantError(f"Failed to dial {number}: {err}") from err

    return dial_service


async def _create_dtmf_service(entry: WebexCEConfigEntry) -> Callable:
    """Create DTMF service handler."""

    async def send_dtmf_service(call: ServiceCall) -> None:
        """Send DTMF tones."""
        client = entry.runtime_data
        dtmf = call.data["dtmf"]
        try:
            await client.xcommand(["Call", "DTMFSend"], DTMFString=dtmf)
        except Exception as err:
            raise HomeAssistantError(f"Failed to send DTMF: {err}") from err

    return send_dtmf_service


async def _create_camera_preset_services(
    entry: WebexCEConfigEntry,
) -> tuple[Callable, Callable]:
    """Create camera preset service handlers."""

    async def activate_service(call: ServiceCall) -> None:
        """Activate a camera preset."""
        client = entry.runtime_data
        preset_id = call.data["preset_id"]
        try:
            await client.xcommand(["Camera", "Preset", "Activate"], PresetId=preset_id)
        except Exception as err:
            raise HomeAssistantError(f"Failed to activate preset: {err}") from err

    async def store_service(call: ServiceCall) -> None:
        """Store a camera preset."""
        client = entry.runtime_data
        preset_id = call.data["preset_id"]
        try:
            await client.xcommand(["Camera", "Preset", "Store"], PresetId=preset_id)
        except Exception as err:
            raise HomeAssistantError(f"Failed to store preset: {err}") from err

    return activate_service, store_service


async def _create_camera_control_services(
    entry: WebexCEConfigEntry,
) -> tuple[Callable, Callable, Callable]:
    """Create camera control service handlers."""

    async def position_set_service(call: ServiceCall) -> None:
        """Set camera position."""
        client = entry.runtime_data
        camera_id = call.data.get("camera_id", 1)
        params = {"CameraId": camera_id}
        if "pan" in call.data:
            params["Pan"] = call.data["pan"]
        if "tilt" in call.data:
            params["Tilt"] = call.data["tilt"]
        if "zoom" in call.data:
            params["Zoom"] = call.data["zoom"]
        try:
            await client.xcommand(["Camera", "PositionSet"], **params)
        except Exception as err:
            raise HomeAssistantError(f"Failed to set camera position: {err}") from err

    async def ramp_service(call: ServiceCall) -> None:
        """Move camera in a direction."""
        client = entry.runtime_data
        camera_id = call.data.get("camera_id", 1)
        direction = call.data["direction"]
        speed = call.data.get("speed", 5)
        try:
            await client.xcommand(
                ["Camera", "Ramp"], CameraId=camera_id, **{direction: speed}
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to move camera: {err}") from err

    async def ramp_stop_service(call: ServiceCall) -> None:
        """Stop camera movement."""
        client = entry.runtime_data
        camera_id = call.data.get("camera_id", 1)
        try:
            await client.xcommand(["Camera", "Ramp"], CameraId=camera_id, Stop={})
        except Exception as err:
            raise HomeAssistantError(f"Failed to stop camera: {err}") from err

    return position_set_service, ramp_service, ramp_stop_service


async def _create_display_services(
    entry: WebexCEConfigEntry,
) -> tuple[Callable, Callable, Callable, Callable]:
    """Create display service handlers."""

    async def display_message_service(call: ServiceCall) -> None:
        """Display a message on the device."""
        client = entry.runtime_data
        text = call.data["text"]
        duration = call.data.get("duration", 10)
        try:
            await client.xcommand(
                ["UserInterface", "Message", "TextLine", "Display"],
                Text=text,
                Duration=duration,
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to display message: {err}") from err

    async def clear_message_service(call: ServiceCall) -> None:
        """Clear displayed message."""
        client = entry.runtime_data
        try:
            await client.xcommand(["UserInterface", "Message", "TextLine", "Clear"])
        except Exception as err:
            raise HomeAssistantError(f"Failed to clear message: {err}") from err

    async def display_webview_service(call: ServiceCall) -> None:
        """Display a web view."""
        client = entry.runtime_data
        url = call.data["url"]
        title = call.data.get("title", "")
        mode = call.data.get("mode", "Modal")
        try:
            params = {"Url": url, "Mode": mode}
            if title:
                params["Title"] = title
            await client.xcommand(["UserInterface", "WebView", "Display"], **params)
        except Exception as err:
            raise HomeAssistantError(f"Failed to display webview: {err}") from err

    async def close_webview_service(call: ServiceCall) -> None:
        """Close web view."""
        client = entry.runtime_data
        try:
            await client.xcommand(["UserInterface", "WebView", "Clear"])
        except Exception as err:
            raise HomeAssistantError(f"Failed to close webview: {err}") from err

    return (
        display_message_service,
        clear_message_service,
        display_webview_service,
        close_webview_service,
    )


async def async_setup_services(hass: HomeAssistant, entry: WebexCEConfigEntry) -> None:
    """Set up services for the Webex CE integration."""
    # Create service handlers
    dial = await _create_dial_service(entry)
    send_dtmf = await _create_dtmf_service(entry)
    preset_activate, preset_store = await _create_camera_preset_services(entry)
    camera_position, camera_ramp, camera_stop = await _create_camera_control_services(
        entry
    )
    display_msg, clear_msg, display_web, close_web = await _create_display_services(
        entry
    )

    # Register services
    hass.services.async_register(DOMAIN, "dial", dial)
    hass.services.async_register(DOMAIN, "send_dtmf", send_dtmf)
    hass.services.async_register(DOMAIN, "camera_preset_activate", preset_activate)
    hass.services.async_register(DOMAIN, "camera_preset_store", preset_store)
    hass.services.async_register(DOMAIN, "camera_position_set", camera_position)
    hass.services.async_register(DOMAIN, "camera_ramp", camera_ramp)
    hass.services.async_register(DOMAIN, "camera_ramp_stop", camera_stop)
    hass.services.async_register(DOMAIN, "display_message", display_msg)
    hass.services.async_register(DOMAIN, "clear_message", clear_msg)
    hass.services.async_register(DOMAIN, "display_webview", display_web)
    hass.services.async_register(DOMAIN, "close_webview", close_web)
