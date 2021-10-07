"""The Energy websocket API."""
from __future__ import annotations

import asyncio
import functools
from types import ModuleType
from typing import Any, Awaitable, Callable, cast

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.singleton import singleton

from .const import DOMAIN
from .data import (
    DEVICE_CONSUMPTION_SCHEMA,
    ENERGY_SOURCE_SCHEMA,
    EnergyManager,
    EnergyPreferencesUpdate,
    async_get_manager,
)
from .types import EnergyPlatform, GetSolarForecastType
from .validate import async_validate

EnergyWebSocketCommandHandler = Callable[
    [HomeAssistant, websocket_api.ActiveConnection, "dict[str, Any]", "EnergyManager"],
    None,
]
AsyncEnergyWebSocketCommandHandler = Callable[
    [HomeAssistant, websocket_api.ActiveConnection, "dict[str, Any]", "EnergyManager"],
    Awaitable[None],
]


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the energy websocket API."""
    websocket_api.async_register_command(hass, ws_get_prefs)
    websocket_api.async_register_command(hass, ws_save_prefs)
    websocket_api.async_register_command(hass, ws_info)
    websocket_api.async_register_command(hass, ws_validate)
    websocket_api.async_register_command(hass, ws_solar_forecast)


@singleton("energy_platforms")
async def async_get_energy_platforms(
    hass: HomeAssistant,
) -> dict[str, GetSolarForecastType]:
    """Get energy platforms."""
    platforms: dict[str, GetSolarForecastType] = {}

    async def _process_energy_platform(
        hass: HomeAssistant, domain: str, platform: ModuleType
    ) -> None:
        """Process energy platforms."""
        if not hasattr(platform, "async_get_solar_forecast"):
            return

        platforms[domain] = cast(EnergyPlatform, platform).async_get_solar_forecast

    await async_process_integration_platforms(hass, DOMAIN, _process_energy_platform)

    return platforms


def _ws_with_manager(
    func: Any,
) -> websocket_api.WebSocketCommandHandler:
    """Decorate a function to pass in a manager."""

    @websocket_api.async_response
    @functools.wraps(func)
    async def with_manager(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        manager = await async_get_manager(hass)

        result = func(hass, connection, msg, manager)

        if asyncio.iscoroutine(result):
            await result

    return with_manager


@websocket_api.websocket_command(
    {
        vol.Required("type"): "energy/get_prefs",
    }
)
@_ws_with_manager
@callback
def ws_get_prefs(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
    manager: EnergyManager,
) -> None:
    """Handle get prefs command."""
    if manager.data is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "No prefs")
        return

    connection.send_result(msg["id"], manager.data)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "energy/save_prefs",
        vol.Optional("energy_sources"): ENERGY_SOURCE_SCHEMA,
        vol.Optional("device_consumption"): [DEVICE_CONSUMPTION_SCHEMA],
    }
)
@_ws_with_manager
async def ws_save_prefs(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
    manager: EnergyManager,
) -> None:
    """Handle get prefs command."""
    msg_id = msg.pop("id")
    msg.pop("type")
    await manager.async_update(cast(EnergyPreferencesUpdate, msg))
    connection.send_result(msg_id, manager.data)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "energy/info",
    }
)
@websocket_api.async_response
async def ws_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Handle get info command."""
    forecast_platforms = await async_get_energy_platforms(hass)
    connection.send_result(
        msg["id"],
        {
            "cost_sensors": hass.data[DOMAIN]["cost_sensors"],
            "solar_forecast_domains": list(forecast_platforms),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "energy/validate",
    }
)
@websocket_api.async_response
async def ws_validate(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Handle validate command."""
    connection.send_result(msg["id"], (await async_validate(hass)).as_dict())


@websocket_api.websocket_command(
    {
        vol.Required("type"): "energy/solar_forecast",
    }
)
@_ws_with_manager
async def ws_solar_forecast(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
    manager: EnergyManager,
) -> None:
    """Handle solar forecast command."""
    if manager.data is None:
        connection.send_result(msg["id"], {})
        return

    config_entries: dict[str, str | None] = {}

    for source in manager.data["energy_sources"]:
        if (
            source["type"] != "solar"
            or source.get("config_entry_solar_forecast") is None
        ):
            continue

        # typing is not catching the above guard for config_entry_solar_forecast being none
        for config_entry in source["config_entry_solar_forecast"]:  # type: ignore[union-attr]
            config_entries[config_entry] = None

    if not config_entries:
        connection.send_result(msg["id"], {})
        return

    forecasts = {}

    forecast_platforms = await async_get_energy_platforms(hass)

    for config_entry_id in config_entries:
        config_entry = hass.config_entries.async_get_entry(config_entry_id)
        # Filter out non-existing config entries or unsupported domains

        if config_entry is None or config_entry.domain not in forecast_platforms:
            continue

        forecast = await forecast_platforms[config_entry.domain](hass, config_entry_id)

        if forecast is not None:
            forecasts[config_entry_id] = forecast

    connection.send_result(msg["id"], forecasts)
