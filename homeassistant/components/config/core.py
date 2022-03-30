"""Component to interact with Hassbian tools."""

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.config import async_check_ha_config_file
from homeassistant.const import CONF_UNIT_SYSTEM_IMPERIAL, CONF_UNIT_SYSTEM_METRIC
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import location


async def async_setup(hass):
    """Set up the Hassbian config."""
    hass.http.register_view(CheckConfigView)
    websocket_api.async_register_command(hass, websocket_update_config)
    websocket_api.async_register_command(hass, websocket_detect_config)
    return True


class CheckConfigView(HomeAssistantView):
    """Hassbian packages endpoint."""

    url = "/api/config/core/check_config"
    name = "api:config:core:check_config"

    async def post(self, request):
        """Validate configuration and return results."""
        errors = await async_check_ha_config_file(request.app["hass"])

        state = "invalid" if errors else "valid"

        return self.json({"result": state, "errors": errors})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "config/core/update",
        vol.Optional("latitude"): cv.latitude,
        vol.Optional("longitude"): cv.longitude,
        vol.Optional("elevation"): int,
        vol.Optional("unit_system"): cv.unit_system,
        vol.Optional("location_name"): str,
        vol.Optional("time_zone"): cv.time_zone,
        vol.Optional("external_url"): vol.Any(cv.url_no_path, None),
        vol.Optional("internal_url"): vol.Any(cv.url_no_path, None),
        vol.Optional("currency"): cv.currency,
    }
)
@websocket_api.async_response
async def websocket_update_config(hass, connection, msg):
    """Handle update core config command."""
    data = dict(msg)
    data.pop("id")
    data.pop("type")

    try:
        await hass.config.async_update(**data)
        connection.send_result(msg["id"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_info", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({"type": "config/core/detect"})
@websocket_api.async_response
async def websocket_detect_config(hass, connection, msg):
    """Detect core config."""
    session = async_get_clientsession(hass)
    location_info = await location.async_detect_location_info(session)

    info = {}

    if location_info is None:
        connection.send_result(msg["id"], info)
        return

    if location_info.use_metric:
        info["unit_system"] = CONF_UNIT_SYSTEM_METRIC
    else:
        info["unit_system"] = CONF_UNIT_SYSTEM_IMPERIAL

    if location_info.latitude:
        info["latitude"] = location_info.latitude

    if location_info.longitude:
        info["longitude"] = location_info.longitude

    if location_info.time_zone:
        info["time_zone"] = location_info.time_zone

    if location_info.currency:
        info["currency"] = location_info.currency

    connection.send_result(msg["id"], info)
