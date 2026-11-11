"""Service registration for System Bridge integration."""

from collections.abc import Awaitable
from dataclasses import asdict
from enum import StrEnum
import logging
from typing import Any

import probatio
from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.keyboard_key import KeyboardKey
from systembridgeconnector.models.keyboard_text import KeyboardText
from systembridgeconnector.models.modules.processes import Process
from systembridgeconnector.models.open_path import OpenPath
from systembridgeconnector.models.open_url import OpenUrl
from systembridgeconnector.models.response import Response

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import (
    CONF_COMMAND,
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PATH,
    CONF_URL,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN
from .coordinator import SystemBridgeConfigEntry, SystemBridgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONF_BRIDGE = "bridge"
CONF_KEY = "key"
CONF_TEXT = "text"

POWER_COMMAND_MAP = {
    "hibernate": "power_hibernate",
    "lock": "power_lock",
    "logout": "power_logout",
    "restart": "power_restart",
    "shutdown": "power_shutdown",
    "sleep": "power_sleep",
}


class SystemBridgeService(StrEnum):
    """Store keys for System Bridge notify entity services."""

    SEND_MESSAGE = "send_message"


class SystemBridgeServiceArgument(StrEnum):
    """Store keys for System Bridge notify entity service arguments."""

    BUTTONS = "buttons"
    DURATION = "duration"
    ICON = "icon"
    MESSAGE = "message"
    PATH = "path"
    SOUND = "sound"
    TITLE = "title"
    URGENCY = "urgency"
    URL = "url"


BUTTON_ID = "id"
BUTTON_LABEL = "label"
# Clicking the notification itself reports this id
BUTTON_ID_DEFAULT = "default"
MAX_BUTTONS = 3
URGENCIES = ["low", "normal", "critical"]
CLICK_ACTION = "click_action"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for System Bridge integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SystemBridgeService.SEND_MESSAGE,
        entity_domain=NOTIFY_DOMAIN,
        schema={
            probatio.Required(SystemBridgeServiceArgument.MESSAGE): cv.string,
            probatio.Optional(SystemBridgeServiceArgument.TITLE): cv.string,
            probatio.Optional(SystemBridgeServiceArgument.ICON): cv.string,
            probatio.Optional(SystemBridgeServiceArgument.URGENCY): probatio.In(
                URGENCIES
            ),
            probatio.Optional(
                SystemBridgeServiceArgument.DURATION
            ): cv.positive_time_period,
            probatio.Optional(SystemBridgeServiceArgument.BUTTONS): probatio.All(
                probatio.EnsureList(),
                [
                    {
                        probatio.Required(BUTTON_ID): probatio.All(
                            cv.string, probatio.NotIn([BUTTON_ID_DEFAULT])
                        ),
                        probatio.Required(BUTTON_LABEL): cv.string,
                    }
                ],
                probatio.Length(max=MAX_BUTTONS),
            ),
            probatio.Optional(SystemBridgeServiceArgument.SOUND): cv.string,
            probatio.Exclusive(
                SystemBridgeServiceArgument.URL, CLICK_ACTION
            ): cv.string,
            probatio.Exclusive(
                SystemBridgeServiceArgument.PATH, CLICK_ACTION
            ): cv.string,
        },
        func="system_bridge_send_message",
        supports_response=SupportsResponse.OPTIONAL,
        # A url or path opens on the host, as open_url and open_path do
        admin_only=True,
        description_placeholders={
            "icon_naming_url": "https://specifications.freedesktop.org/icon-naming/latest/"
        },
    )

    hass.services.async_register(
        DOMAIN,
        "get_process_by_id",
        handle_get_process_by_id,
        schema=probatio.Schema(
            {
                probatio.Required(CONF_BRIDGE): cv.string,
                probatio.Required(CONF_ID): cv.positive_int,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "get_processes_by_name",
        handle_get_processes_by_name,
        schema=probatio.Schema(
            {
                probatio.Required(CONF_BRIDGE): cv.string,
                probatio.Required(CONF_NAME): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_admin_service(
        hass,
        DOMAIN,
        "open_path",
        handle_open_path,
        schema=probatio.Schema(
            {
                probatio.Required(CONF_BRIDGE): cv.string,
                probatio.Required(CONF_PATH): cv.string,
            },
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )

    service.async_register_admin_service(
        hass,
        DOMAIN,
        "power_command",
        handle_power_command,
        schema=probatio.Schema(
            {
                probatio.Required(CONF_BRIDGE): cv.string,
                probatio.Required(CONF_COMMAND): probatio.In(POWER_COMMAND_MAP),
            },
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )

    service.async_register_admin_service(
        hass,
        DOMAIN,
        "open_url",
        handle_open_url,
        schema=probatio.Schema(
            {
                probatio.Required(CONF_BRIDGE): cv.string,
                probatio.Required(CONF_URL): cv.string,
            },
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )

    service.async_register_admin_service(
        hass,
        DOMAIN,
        "send_keypress",
        handle_send_keypress,
        schema=probatio.Schema(
            {
                probatio.Required(CONF_BRIDGE): cv.string,
                probatio.Required(CONF_KEY): cv.string,
            },
        ),
        supports_response=SupportsResponse.OPTIONAL,
        description_placeholders={
            "syntax_keys_documentation_url": "https://robotjs.dev/docs/syntax#keys"
        },
    )

    service.async_register_admin_service(
        hass,
        DOMAIN,
        "send_text",
        handle_send_text,
        schema=probatio.Schema(
            {
                probatio.Required(CONF_BRIDGE): cv.string,
                probatio.Required(CONF_TEXT): cv.string,
            },
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )


def _get_coordinator(
    hass: HomeAssistant, device_id: str
) -> SystemBridgeDataUpdateCoordinator:
    """Return the coordinator for a device id."""
    entry: SystemBridgeConfigEntry
    _, entry = service.async_get_device_and_config_entry(hass, DOMAIN, device_id)
    return entry.runtime_data


async def handle_get_process_by_id(service_call: ServiceCall) -> ServiceResponse:
    """Handle the get process by id service call."""
    _LOGGER.debug("Get process by id: %s", service_call.data)
    coordinator = _get_coordinator(service_call.hass, service_call.data[CONF_BRIDGE])
    processes: list[Process] = coordinator.data.processes

    # Find process.id from list, raise ServiceValidationError if not found
    try:
        return asdict(
            next(
                process
                for process in processes
                if process.id == service_call.data[CONF_ID]
            )
        )
    except StopIteration as e:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="process_not_found",
            translation_placeholders={"id": service_call.data[CONF_ID]},
        ) from e


async def handle_get_processes_by_name(
    service_call: ServiceCall,
) -> ServiceResponse:
    """Handle the get process by name service call."""
    _LOGGER.debug("Get process by name: %s", service_call.data)
    coordinator = _get_coordinator(service_call.hass, service_call.data[CONF_BRIDGE])

    # Find processes from list
    items: list[dict[str, Any]] = [
        asdict(process)
        for process in coordinator.data.processes
        if process.name is not None
        and service_call.data[CONF_NAME].lower() in process.name.lower()
    ]

    return {
        "count": len(items),
        "processes": list(items),
    }


async def _async_send_command(
    coordinator: SystemBridgeDataUpdateCoordinator,
    action: str,
    command: Awaitable[Response],
) -> ServiceResponse:
    """Send a command to the bridge, raising on a closed connection or an error."""
    try:
        response = await command
    except (ConnectionClosedException, ConnectionResetError) as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
            translation_placeholders={
                "title": coordinator.config_entry.title,
                "host": coordinator.config_entry.data[CONF_HOST],
            },
        ) from e
    if response.type == EventType.ERROR:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="action_failed",
            translation_placeholders={
                "action": action,
                "error": response.message or "",
            },
        )
    return asdict(response)


async def handle_open_path(service_call: ServiceCall) -> ServiceResponse:
    """Handle the open path service call."""
    _LOGGER.debug("Open path: %s", service_call.data)
    coordinator = _get_coordinator(service_call.hass, service_call.data[CONF_BRIDGE])
    return await _async_send_command(
        coordinator,
        service_call.service,
        coordinator.websocket_client.open_path(
            OpenPath(path=service_call.data[CONF_PATH])
        ),
    )


async def handle_power_command(service_call: ServiceCall) -> ServiceResponse:
    """Handle the power command service call."""
    _LOGGER.debug("Power command: %s", service_call.data)
    coordinator = _get_coordinator(service_call.hass, service_call.data[CONF_BRIDGE])
    return await _async_send_command(
        coordinator,
        service_call.service,
        getattr(
            coordinator.websocket_client,
            POWER_COMMAND_MAP[service_call.data[CONF_COMMAND]],
        )(),
    )


async def handle_open_url(service_call: ServiceCall) -> ServiceResponse:
    """Handle the open url service call."""
    _LOGGER.debug("Open URL: %s", service_call.data)
    coordinator = _get_coordinator(service_call.hass, service_call.data[CONF_BRIDGE])
    return await _async_send_command(
        coordinator,
        service_call.service,
        coordinator.websocket_client.open_url(OpenUrl(url=service_call.data[CONF_URL])),
    )


async def handle_send_keypress(service_call: ServiceCall) -> ServiceResponse:
    """Handle the send_keypress service call."""
    coordinator = _get_coordinator(service_call.hass, service_call.data[CONF_BRIDGE])
    return await _async_send_command(
        coordinator,
        service_call.service,
        coordinator.websocket_client.keyboard_keypress(
            KeyboardKey(key=service_call.data[CONF_KEY])
        ),
    )


async def handle_send_text(service_call: ServiceCall) -> ServiceResponse:
    """Handle the send_text service call."""
    coordinator = _get_coordinator(service_call.hass, service_call.data[CONF_BRIDGE])
    return await _async_send_command(
        coordinator,
        service_call.service,
        coordinator.websocket_client.keyboard_text(
            KeyboardText(text=service_call.data[CONF_TEXT])
        ),
    )
