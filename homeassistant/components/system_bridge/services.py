"""Service registration for System Bridge integration."""

from dataclasses import asdict
import logging
from typing import Any

from systembridgeconnector.models.keyboard_key import KeyboardKey
from systembridgeconnector.models.keyboard_text import KeyboardText
from systembridgeconnector.models.modules.processes import Process
from systembridgeconnector.models.open_path import OpenPath
from systembridgeconnector.models.open_url import OpenUrl
import voluptuous as vol

from homeassistant.const import CONF_COMMAND, CONF_ID, CONF_NAME, CONF_PATH, CONF_URL
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    service,
)

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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for System Bridge integration."""

    hass.services.async_register(
        DOMAIN,
        "get_process_by_id",
        handle_get_process_by_id,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): cv.string,
                vol.Required(CONF_ID): cv.positive_int,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "get_processes_by_name",
        handle_get_processes_by_name,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): cv.string,
                vol.Required(CONF_NAME): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "open_path",
        handle_open_path,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): cv.string,
                vol.Required(CONF_PATH): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "power_command",
        handle_power_command,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): cv.string,
                vol.Required(CONF_COMMAND): vol.In(POWER_COMMAND_MAP),
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "open_url",
        handle_open_url,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): cv.string,
                vol.Required(CONF_URL): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "send_keypress",
        handle_send_keypress,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): cv.string,
                vol.Required(CONF_KEY): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
        description_placeholders={
            "syntax_keys_documentation_url": "https://robotjs.dev/docs/syntax#keys"
        },
    )

    hass.services.async_register(
        DOMAIN,
        "send_text",
        handle_send_text,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): cv.string,
                vol.Required(CONF_TEXT): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )


def _get_coordinator(
    hass: HomeAssistant, device_id: str
) -> SystemBridgeDataUpdateCoordinator:
    """Return the coordinator for a device id."""

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)

    if device_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device": device_id},
        )
    try:
        entry_id = next(
            entry.entry_id
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.entry_id in device_entry.config_entries
        )
    except StopIteration as e:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device": device_id},
        ) from e
    entry: SystemBridgeConfigEntry = service.async_get_config_entry(
        hass, DOMAIN, entry_id
    )
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


async def handle_open_path(service_call: ServiceCall) -> ServiceResponse:
    """Handle the open path service call."""
    _LOGGER.debug("Open path: %s", service_call.data)
    coordinator = _get_coordinator(service_call.hass, service_call.data[CONF_BRIDGE])
    response = await coordinator.websocket_client.open_path(
        OpenPath(path=service_call.data[CONF_PATH])
    )
    return asdict(response)


async def handle_power_command(service_call: ServiceCall) -> ServiceResponse:
    """Handle the power command service call."""
    _LOGGER.debug("Power command: %s", service_call.data)
    coordinator = _get_coordinator(service_call.hass, service_call.data[CONF_BRIDGE])
    response = await getattr(
        coordinator.websocket_client,
        POWER_COMMAND_MAP[service_call.data[CONF_COMMAND]],
    )()
    return asdict(response)


async def handle_open_url(service_call: ServiceCall) -> ServiceResponse:
    """Handle the open url service call."""
    _LOGGER.debug("Open URL: %s", service_call.data)
    coordinator = _get_coordinator(service_call.hass, service_call.data[CONF_BRIDGE])
    response = await coordinator.websocket_client.open_url(
        OpenUrl(url=service_call.data[CONF_URL])
    )
    return asdict(response)


async def handle_send_keypress(service_call: ServiceCall) -> ServiceResponse:
    """Handle the send_keypress service call."""
    coordinator = _get_coordinator(service_call.hass, service_call.data[CONF_BRIDGE])
    response = await coordinator.websocket_client.keyboard_keypress(
        KeyboardKey(key=service_call.data[CONF_KEY])
    )
    return asdict(response)


async def handle_send_text(service_call: ServiceCall) -> ServiceResponse:
    """Handle the send_text service call."""
    coordinator = _get_coordinator(service_call.hass, service_call.data[CONF_BRIDGE])
    response = await coordinator.websocket_client.keyboard_text(
        KeyboardText(text=service_call.data[CONF_TEXT])
    )
    return asdict(response)
