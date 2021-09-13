"""The Energy websocket API."""
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .statistics import validate_statistics


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the recorder websocket API."""
    websocket_api.async_register_command(hass, ws_validate_statistics)


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
