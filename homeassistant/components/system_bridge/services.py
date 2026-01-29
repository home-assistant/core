"""Handle System Bridge Service calls."""

from __future__ import annotations

from dataclasses import asdict
import logging
from typing import Any

from systembridgeconnector.exceptions import (
    BadRequestException,
    ConnectionErrorException,
)
from systembridgeconnector.models.command_execute import ExecuteRequest
from systembridgeconnector.models.keyboard_key import KeyboardKey
from systembridgeconnector.models.keyboard_text import KeyboardText
from systembridgeconnector.models.modules.processes import Process
from systembridgeconnector.models.open_path import OpenPath
from systembridgeconnector.models.open_url import OpenUrl
import voluptuous as vol

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
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONF_BRIDGE = "bridge"
CONF_COMMAND_ID = "command_id"
CONF_KEY = "key"
CONF_TEXT = "text"

SERVICE_EXECUTE_COMMAND = "execute_command"
SERVICE_GET_COMMANDS = "get_commands"
SERVICE_GET_PROCESS_BY_ID = "get_process_by_id"
SERVICE_GET_PROCESSES_BY_NAME = "get_processes_by_name"
SERVICE_OPEN_PATH = "open_path"
SERVICE_POWER_COMMAND = "power_command"
SERVICE_OPEN_URL = "open_url"
SERVICE_SEND_KEYPRESS = "send_keypress"
SERVICE_SEND_TEXT = "send_text"

POWER_COMMAND_MAP = {
    "hibernate": "power_hibernate",
    "lock": "power_lock",
    "logout": "power_logout",
    "restart": "power_restart",
    "shutdown": "power_shutdown",
    "sleep": "power_sleep",
}


def _valid_device(hass: HomeAssistant, device: str) -> str:
    """Check device is valid."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device)
    if device_entry is not None:
        try:
            return next(
                entry.entry_id
                for entry in hass.config_entries.async_entries(DOMAIN)
                if entry.entry_id in device_entry.config_entries
            )
        except StopIteration as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"device": device},
            ) from exception
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="device_not_found",
        translation_placeholders={"device": device},
    )


async def _handle_get_process_by_id(service_call: ServiceCall) -> ServiceResponse:
    """Handle the get process by id service call."""
    _LOGGER.debug("Get process by id: %s", service_call.data)
    coordinator: SystemBridgeDataUpdateCoordinator = service_call.hass.data[DOMAIN][
        service_call.data[CONF_BRIDGE]
    ]
    processes: list[Process] = coordinator.data.processes

    try:
        return asdict(
            next(
                process
                for process in processes
                if process.id == service_call.data[CONF_ID]
            )
        )
    except StopIteration as exception:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="process_not_found",
            translation_placeholders={"id": service_call.data[CONF_ID]},
        ) from exception


async def _handle_get_commands(service_call: ServiceCall) -> ServiceResponse:
    """Handle the get commands service call."""
    _LOGGER.debug("Get commands: %s", service_call.data)
    coordinator: SystemBridgeDataUpdateCoordinator = service_call.hass.data[DOMAIN][
        service_call.data[CONF_BRIDGE]
    ]

    try:
        commands = await coordinator.websocket_client.get_commands()

        return {
            "count": len(commands.allowlist),
            "commands": [asdict(command) for command in commands.allowlist],
        }
    except ConnectionErrorException as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
            translation_placeholders={
                "title": coordinator.title,
                "host": coordinator.config_entry.data[CONF_HOST],
            },
        ) from err
    except Exception as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_execution_failed",
            translation_placeholders={"error": str(err)},
        ) from err


async def _handle_get_processes_by_name(
    service_call: ServiceCall,
) -> ServiceResponse:
    """Handle the get process by name service call."""
    _LOGGER.debug("Get process by name: %s", service_call.data)
    coordinator: SystemBridgeDataUpdateCoordinator = service_call.hass.data[DOMAIN][
        service_call.data[CONF_BRIDGE]
    ]

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


async def _handle_open_path(service_call: ServiceCall) -> ServiceResponse:
    """Handle the open path service call."""
    _LOGGER.debug("Open path: %s", service_call.data)
    coordinator: SystemBridgeDataUpdateCoordinator = service_call.hass.data[DOMAIN][
        service_call.data[CONF_BRIDGE]
    ]
    response = await coordinator.websocket_client.open_path(
        OpenPath(path=service_call.data[CONF_PATH])
    )
    return asdict(response)


async def _handle_power_command(service_call: ServiceCall) -> ServiceResponse:
    """Handle the power command service call."""
    _LOGGER.debug("Power command: %s", service_call.data)
    coordinator: SystemBridgeDataUpdateCoordinator = service_call.hass.data[DOMAIN][
        service_call.data[CONF_BRIDGE]
    ]
    response = await getattr(
        coordinator.websocket_client,
        POWER_COMMAND_MAP[service_call.data[CONF_COMMAND]],
    )()
    return asdict(response)


async def _handle_open_url(service_call: ServiceCall) -> ServiceResponse:
    """Handle the open url service call."""
    _LOGGER.debug("Open URL: %s", service_call.data)
    coordinator: SystemBridgeDataUpdateCoordinator = service_call.hass.data[DOMAIN][
        service_call.data[CONF_BRIDGE]
    ]
    response = await coordinator.websocket_client.open_url(
        OpenUrl(url=service_call.data[CONF_URL])
    )
    return asdict(response)


async def _handle_send_keypress(service_call: ServiceCall) -> ServiceResponse:
    """Handle the send_keypress service call."""
    coordinator: SystemBridgeDataUpdateCoordinator = service_call.hass.data[DOMAIN][
        service_call.data[CONF_BRIDGE]
    ]
    response = await coordinator.websocket_client.keyboard_keypress(
        KeyboardKey(key=service_call.data[CONF_KEY])
    )
    return asdict(response)


async def _handle_send_text(service_call: ServiceCall) -> ServiceResponse:
    """Handle the send_text service call."""
    coordinator: SystemBridgeDataUpdateCoordinator = service_call.hass.data[DOMAIN][
        service_call.data[CONF_BRIDGE]
    ]
    response = await coordinator.websocket_client.keyboard_text(
        KeyboardText(text=service_call.data[CONF_TEXT])
    )
    return asdict(response)


async def _handle_execute_command(service_call: ServiceCall) -> ServiceResponse:
    """Handle the execute command service call."""
    _LOGGER.debug("Execute command: %s", service_call.data)
    bridge_entry_id = service_call.data[CONF_BRIDGE]
    coordinator: SystemBridgeDataUpdateCoordinator = service_call.hass.data[DOMAIN][
        bridge_entry_id
    ]

    try:
        result = await coordinator.websocket_client.execute_command(
            ExecuteRequest(commandID=service_call.data[CONF_COMMAND_ID]),
            timeout=service_call.data.get("timeout", 300.0),
        )
        return asdict(result)
    except BadRequestException as err:
        error_msg = str(err)
        if "COMMAND_NOT_FOUND" in error_msg or "command not found" in error_msg.lower():
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="command_not_found",
                translation_placeholders={
                    "command_id": service_call.data[CONF_COMMAND_ID],
                },
            ) from err
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_execution_failed",
            translation_placeholders={"error": error_msg},
        ) from err
    except ConnectionErrorException as err:
        error_msg = str(err)
        if "timeout" in error_msg.lower() or "TIMEOUT" in error_msg:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_timeout",
                translation_placeholders={
                    "timeout": str(service_call.data.get("timeout", 300.0)),
                },
            ) from err
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_execution_failed",
            translation_placeholders={"error": error_msg},
        ) from err
    except Exception as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_execution_failed",
            translation_placeholders={"error": str(err)},
        ) from err


def async_setup_services(hass: HomeAssistant) -> None:
    """Register all System Bridge services."""
    if hass.services.has_service(DOMAIN, SERVICE_OPEN_URL):
        return

    def valid_device(device: str) -> str:
        """Check device is valid."""
        return _valid_device(hass, device)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PROCESS_BY_ID,
        _handle_get_process_by_id,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_ID): cv.positive_int,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PROCESSES_BY_NAME,
        _handle_get_processes_by_name,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_NAME): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_COMMANDS,
        _handle_get_commands,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_OPEN_PATH,
        _handle_open_path,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_PATH): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_POWER_COMMAND,
        _handle_power_command,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_COMMAND): vol.In(POWER_COMMAND_MAP),
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_OPEN_URL,
        _handle_open_url,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_URL): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_KEYPRESS,
        _handle_send_keypress,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_KEY): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
        description_placeholders={
            "syntax_keys_documentation_url": "http://robotjs.io/docs/syntax#keys"
        },
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_TEXT,
        _handle_send_text,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_TEXT): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_EXECUTE_COMMAND,
        _handle_execute_command,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_COMMAND_ID): cv.string,
                vol.Optional("timeout", default=300.0): cv.positive_float,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )
