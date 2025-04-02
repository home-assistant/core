"""Support for System health ."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
import dataclasses
from datetime import datetime
import logging
from typing import Any, Protocol

import aiohttp
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    integration_platform,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

DOMAIN = "system_health"

INFO_CALLBACK_TIMEOUT = 5

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


class SystemHealthProtocol(Protocol):
    """Define the format of system_health platforms."""

    def async_register(
        self, hass: HomeAssistant, register: SystemHealthRegistration
    ) -> None:
        """Register system health callbacks."""


@bind_hass
@callback
def async_register_info(
    hass: HomeAssistant,
    domain: str,
    info_callback: Callable[[HomeAssistant], Awaitable[dict]],
) -> None:
    """Register an info callback.

    Deprecated.
    """
    _LOGGER.warning(
        "Calling system_health.async_register_info is deprecated; Add a system_health"
        " platform instead"
    )
    hass.data.setdefault(DOMAIN, {})
    SystemHealthRegistration(hass, domain).async_register_info(info_callback)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the System Health component."""
    websocket_api.async_register_command(hass, handle_info)
    hass.data.setdefault(DOMAIN, {})

    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _register_system_health_platform
    )

    return True


@callback
def _register_system_health_platform(
    hass: HomeAssistant, integration_domain: str, platform: SystemHealthProtocol
) -> None:
    """Register a system health platform."""
    platform.async_register(hass, SystemHealthRegistration(hass, integration_domain))


async def get_integration_info(
    hass: HomeAssistant, registration: SystemHealthRegistration
) -> dict[str, Any]:
    """Get integration system health."""
    try:
        assert registration.info_callback
        async with asyncio.timeout(INFO_CALLBACK_TIMEOUT):
            data = await registration.info_callback(hass)
    except TimeoutError:
        data = {"error": {"type": "failed", "error": "timeout"}}
    except Exception:
        _LOGGER.exception("Error fetching info")
        data = {"error": {"type": "failed", "error": "unknown"}}

    result: dict[str, Any] = {"info": data}

    if registration.manage_url:
        result["manage_url"] = registration.manage_url

    return result


async def _registered_domain_data(
    hass: HomeAssistant,
) -> AsyncGenerator[tuple[str, dict[str, Any]]]:
    registrations: dict[str, SystemHealthRegistration] = hass.data[DOMAIN]
    for domain, domain_data in zip(
        registrations,
        await asyncio.gather(
            *(
                get_integration_info(hass, registration)
                for registration in registrations.values()
            )
        ),
        strict=False,
    ):
        yield domain, domain_data


async def get_info(hass: HomeAssistant) -> dict[str, dict[str, str]]:
    """Get the full set of system health information."""
    domains: dict[str, dict[str, Any]] = {}

    async def _get_info_value(value: Any) -> Any:
        if not asyncio.iscoroutine(value):
            return value
        try:
            return await value
        except Exception as exception:
            _LOGGER.exception("Error fetching system info for %s - %s", domain, key)
            return f"Exception: {exception}"

    async for domain, domain_data in _registered_domain_data(hass):
        domain_info: dict[str, Any] = {}
        for key, value in domain_data["info"].items():
            info_value = await _get_info_value(value)

            if isinstance(info_value, datetime):
                domain_info[key] = info_value.isoformat()
            elif (
                isinstance(info_value, dict)
                and "type" in info_value
                and info_value["type"] == "failed"
            ):
                domain_info[key] = f"Failed: {info_value.get('error', 'unknown')}"
            else:
                domain_info[key] = info_value

        domains[domain] = domain_info

    return domains


@callback
def _format_value(val: Any) -> Any:
    """Format a system health value."""
    if isinstance(val, datetime):
        return {"value": val.isoformat(), "type": "date"}
    return val


@websocket_api.websocket_command({vol.Required("type"): "system_health/info"})
@websocket_api.async_response
async def handle_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle an info request via a subscription."""
    data = {}
    pending_info: dict[tuple[str, str], asyncio.Task] = {}

    async for domain, domain_data in _registered_domain_data(hass):
        for key, value in domain_data["info"].items():
            if asyncio.iscoroutine(value):
                value = asyncio.create_task(value)
            if isinstance(value, asyncio.Task):
                pending_info[(domain, key)] = value
                domain_data["info"][key] = {"type": "pending"}
            else:
                domain_data["info"][key] = _format_value(value)

        data[domain] = domain_data

    # Confirm subscription
    connection.send_result(msg["id"])

    stop_event = asyncio.Event()
    connection.subscriptions[msg["id"]] = stop_event.set

    # Send initial data
    connection.send_message(
        websocket_api.messages.event_message(
            msg["id"], {"type": "initial", "data": data}
        )
    )

    # If nothing pending, wrap it up.
    if not pending_info:
        connection.send_message(
            websocket_api.messages.event_message(msg["id"], {"type": "finish"})
        )
        return

    tasks: set[asyncio.Task] = {
        asyncio.create_task(stop_event.wait()),
        *pending_info.values(),
    }
    pending_lookup = {val: key for key, val in pending_info.items()}

    # One task is the stop_event.wait() and is always there
    while len(tasks) > 1 and not stop_event.is_set():
        # Wait for first completed task
        done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        if stop_event.is_set():
            for task in tasks:
                task.cancel()
            return

        # Update subscription of all finished tasks
        for result in done:
            domain, key = pending_lookup[result]
            event_msg: dict[str, Any] = {
                "type": "update",
                "domain": domain,
                "key": key,
            }

            if exception := result.exception():
                _LOGGER.error(
                    "Error fetching system info for %s - %s",
                    domain,
                    key,
                    exc_info=(type(exception), exception, exception.__traceback__),
                )
                event_msg["success"] = False
                event_msg["error"] = {"type": "failed", "error": "unknown"}
            else:
                event_msg["success"] = True
                event_msg["data"] = _format_value(result.result())

            connection.send_message(
                websocket_api.messages.event_message(msg["id"], event_msg)
            )

    connection.send_message(
        websocket_api.messages.event_message(msg["id"], {"type": "finish"})
    )


@dataclasses.dataclass(slots=True)
class SystemHealthRegistration:
    """Helper class to track platform registration."""

    hass: HomeAssistant
    domain: str
    info_callback: Callable[[HomeAssistant], Awaitable[dict]] | None = None
    manage_url: str | None = None

    @callback
    def async_register_info(
        self,
        info_callback: Callable[[HomeAssistant], Awaitable[dict]],
        manage_url: str | None = None,
    ) -> None:
        """Register an info callback."""
        self.info_callback = info_callback
        self.manage_url = manage_url
        self.hass.data[DOMAIN][self.domain] = self


async def async_check_can_reach_url(
    hass: HomeAssistant, url: str, more_info: str | None = None
) -> str | dict[str, str]:
    """Test if the url can be reached."""
    session = aiohttp_client.async_get_clientsession(hass)

    try:
        await session.get(url, timeout=aiohttp.ClientTimeout(total=5))
    except aiohttp.ClientError:
        data = {"type": "failed", "error": "unreachable"}
    except TimeoutError:
        data = {"type": "failed", "error": "timeout"}
    else:
        return "ok"
    if more_info is not None:
        data["more_info"] = more_info
    return data
