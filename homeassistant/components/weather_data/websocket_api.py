"""The Weather data websocket API."""

from typing import Any, cast

import probatio

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .data import WeatherDataPreferencesUpdate, async_get_manager
from .sources import async_get_info


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the Weather data websocket API."""
    websocket_api.async_register_command(hass, ws_get_prefs)
    websocket_api.async_register_command(hass, ws_save_prefs)
    websocket_api.async_register_command(hass, ws_get_info)


@websocket_api.websocket_command({probatio.Required("type"): "weather_data/get_prefs"})
@websocket_api.async_response
async def ws_get_prefs(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle the get prefs command."""
    manager = await async_get_manager(hass)
    connection.send_result(msg["id"], manager.data)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "weather_data/save_prefs",
        probatio.Optional("weather_entities"): [cv.entity_id],
        probatio.Optional("excluded_weather_entities"): [cv.entity_id],
        probatio.Optional("rain_gauge_entity"): probatio.Any(cv.entity_id, None),
        probatio.Optional("air_quality_entities"): [cv.entity_id],
        probatio.Optional("pollen_entities"): [cv.entity_id],
    }
)
@websocket_api.async_response
async def ws_save_prefs(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle the save prefs command."""
    manager = await async_get_manager(hass)
    msg_id = msg.pop("id")
    msg.pop("type")
    manager.async_update(cast(WeatherDataPreferencesUpdate, msg))
    connection.send_result(msg_id, manager.data)


@websocket_api.websocket_command({probatio.Required("type"): "weather_data/get_info"})
@websocket_api.async_response
async def ws_get_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle the get info command."""
    manager = await async_get_manager(hass)
    connection.send_result(msg["id"], await async_get_info(hass, manager.data))
