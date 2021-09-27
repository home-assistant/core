"""The Energy websocket API."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DATA_INSTANCE
from .statistics import validate_statistics


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the recorder websocket API."""
    websocket_api.async_register_command(hass, ws_validate_statistics)
    websocket_api.async_register_command(hass, ws_clear_statistics)
    websocket_api.async_register_command(hass, ws_update_statistics_metadata)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/validate_statistics",
    }
)
@websocket_api.async_response
async def ws_validate_statistics(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Fetch a list of available statistic_id."""
    statistic_ids = await hass.async_add_executor_job(
        validate_statistics,
        hass,
    )
    connection.send_result(msg["id"], statistic_ids)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/clear_statistics",
        vol.Required("statistic_ids"): [str],
    }
)
@callback
def ws_clear_statistics(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Clear statistics for a list of statistic_ids.

    Note: The WS call posts a job to the recorder's queue and then returns, it doesn't
    wait until the job is completed.
    """
    hass.data[DATA_INSTANCE].async_clear_statistics(msg["statistic_ids"])
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/update_statistics_metadata",
        vol.Required("statistic_id"): str,
        vol.Required("unit_of_measurement"): vol.Any(str, None),
    }
)
@callback
def ws_update_statistics_metadata(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Update statistics metadata for a statistic_id."""
    hass.data[DATA_INSTANCE].async_update_statistics_metadata(
        msg["statistic_id"], msg["unit_of_measurement"]
    )
    connection.send_result(msg["id"])
