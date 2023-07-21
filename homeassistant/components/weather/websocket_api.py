"""The weather websocket API."""
from __future__ import annotations

from typing import Any, Literal

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent

from .const import DOMAIN, VALID_UNITS, WeatherEntityFeature

FORECAST_TYPE_TO_FLAG = {
    "daily": WeatherEntityFeature.FORECAST_DAILY,
    "hourly": WeatherEntityFeature.FORECAST_HOURLY,
    "twice_daily": WeatherEntityFeature.FORECAST_TWICE_DAILY,
}


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the weather websocket API."""
    websocket_api.async_register_command(hass, ws_convertible_units)
    websocket_api.async_register_command(hass, ws_subscribe_forecast)


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "weather/convertible_units",
    }
)
def ws_convertible_units(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return supported units for a device class."""
    sorted_units = {
        key: sorted(units, key=str.casefold) for key, units in VALID_UNITS.items()
    }
    connection.send_result(msg["id"], {"units": sorted_units})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "weather/subscribe_forecast",
        vol.Required("entity_id"): cv.entity_domain(DOMAIN),
        vol.Required("forecast_type"): vol.In(["daily", "hourly", "twice_daily"]),
    }
)
@websocket_api.async_response
async def ws_subscribe_forecast(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Subscribe to weather forecasts."""
    from . import WeatherEntity  # pylint: disable=import-outside-toplevel

    component: EntityComponent[WeatherEntity] = hass.data[DOMAIN]
    entity_id: str = msg["entity_id"]
    forecast_type: Literal["daily", "hourly", "twice_daily"] = msg["forecast_type"]

    if not (entity := component.get_entity(msg["entity_id"])):
        connection.send_error(
            msg["id"],
            "invalid_entity_id",
            f"Weather entity not found: {entity_id}",
        )
        return

    if (
        entity.supported_features is None
        or not entity.supported_features & FORECAST_TYPE_TO_FLAG[forecast_type]
    ):
        connection.send_error(
            msg["id"],
            "forecast_not_supported",
            f"The weather entity does not support forecast type: {forecast_type}",
        )
        return

    @callback
    def forecast_listener(forecast: list[dict[str, Any]] | None) -> None:
        """Push a new forecast to websocket."""
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "type": forecast_type,
                    "forecast": forecast,
                },
            )
        )

    connection.subscriptions[msg["id"]] = entity.async_subscribe_forecast(
        forecast_type, forecast_listener
    )
    connection.send_message(websocket_api.result_message(msg["id"]))

    # Push an initial forecast update
    await entity.async_update_listeners({forecast_type})
