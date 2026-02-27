"""Services for madVR Envy integration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from madvr_envy.integration_bridge import action_names, resolve_action_method

from .const import DOMAIN, SERVICE_ACTIVATE_PROFILE, SERVICE_PRESS_KEY, SERVICE_RUN_ACTION
from .models import MadvrEnvyRuntimeData

_SERVICE_ACTIONS = action_names()


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    if hass.services.has_service(DOMAIN, SERVICE_PRESS_KEY):
        return

    async def handle_press_key(call: ServiceCall) -> None:
        runtime_data = _resolve_runtime_data(hass, call.data.get("entry_id"))
        key = str(call.data["key"])
        await _run_per_entry(runtime_data, lambda item: item.client.key_press(key))

    async def handle_activate_profile(call: ServiceCall) -> None:
        runtime_data = _resolve_runtime_data(hass, call.data.get("entry_id"))
        group_id = str(call.data["group_id"])
        profile_index = int(call.data["profile_index"])
        await _run_per_entry(
            runtime_data,
            lambda item: item.client.activate_profile(group_id, profile_index),
        )

    async def handle_run_action(call: ServiceCall) -> None:
        runtime_data = _resolve_runtime_data(hass, call.data.get("entry_id"))
        action = str(call.data["action"])
        await _run_per_entry(
            runtime_data,
            lambda item: resolve_action_method(item.client, action)(),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PRESS_KEY,
        handle_press_key,
        schema=vol.Schema(
            {
                vol.Required("key"): str,
                vol.Optional("entry_id"): str,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ACTIVATE_PROFILE,
        handle_activate_profile,
        schema=vol.Schema(
            {
                vol.Required("group_id"): str,
                vol.Required("profile_index"): vol.Coerce(int),
                vol.Optional("entry_id"): str,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RUN_ACTION,
        handle_run_action,
        schema=vol.Schema(
            {
                vol.Required("action"): vol.In(_SERVICE_ACTIONS),
                vol.Optional("entry_id"): str,
            }
        ),
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload integration services."""
    for service in (SERVICE_PRESS_KEY, SERVICE_ACTIVATE_PROFILE, SERVICE_RUN_ACTION):
        hass.services.async_remove(DOMAIN, service)


def _resolve_runtime_data(
    hass: HomeAssistant, entry_id: object | None
) -> list[MadvrEnvyRuntimeData]:
    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data:
        raise HomeAssistantError("No madVR entries are currently loaded")

    if isinstance(entry_id, str) and entry_id:
        runtime_data = domain_data.get(entry_id)
        if runtime_data is None:
            raise HomeAssistantError(f"Unknown madVR entry_id: {entry_id}")
        return [runtime_data]

    if len(domain_data) > 1:
        raise HomeAssistantError(
            "Multiple madVR entries are loaded. Provide an entry_id."
        )

    return list(domain_data.values())


async def _run_per_entry(
    runtime_data: list[MadvrEnvyRuntimeData],
    command: Callable[[MadvrEnvyRuntimeData], Awaitable[object]],
) -> None:
    results = await asyncio.gather(
        *(command(item) for item in runtime_data),
        return_exceptions=True,
    )
    failures = [result for result in results if isinstance(result, Exception)]
    if not failures:
        return

    if len(runtime_data) == 1:
        raise HomeAssistantError(str(failures[0])) from failures[0]
