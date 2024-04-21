"""Component to interact with Hassbian tools."""

from __future__ import annotations

from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.http import KEY_HASS, HomeAssistantView, require_admin
from homeassistant.components.sensor import async_update_suggested_units
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import check_config, config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import location, unit_system


@callback
def async_setup(hass: HomeAssistant) -> bool:
    """Set up the Hassbian config."""
    hass.http.register_view(CheckConfigView)
    websocket_api.async_register_command(hass, websocket_update_config)
    websocket_api.async_register_command(hass, websocket_detect_config)
    return True


class CheckConfigView(HomeAssistantView):
    """Hassbian packages endpoint."""

    url = "/api/config/core/check_config"
    name = "api:config:core:check_config"

    @require_admin
    async def post(self, request: web.Request) -> web.Response:
        """Validate configuration and return results."""

        res = await check_config.async_check_ha_config_file(request.app[KEY_HASS])

        state = "invalid" if res.errors else "valid"

        return self.json(
            {
                "result": state,
                "errors": res.error_str or None,
                "warnings": res.warning_str or None,
            }
        )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "config/core/update",
        vol.Optional("country"): cv.country,
        vol.Optional("currency"): cv.currency,
        vol.Optional("elevation"): int,
        vol.Optional("external_url"): vol.Any(cv.url_no_path, None),
        vol.Optional("internal_url"): vol.Any(cv.url_no_path, None),
        vol.Optional("language"): cv.language,
        vol.Optional("latitude"): cv.latitude,
        vol.Optional("location_name"): str,
        vol.Optional("longitude"): cv.longitude,
        vol.Optional("time_zone"): cv.time_zone,
        vol.Optional("update_units"): bool,
        vol.Optional("unit_system"): unit_system.validate_unit_system,
    }
)
@websocket_api.async_response
async def websocket_update_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle update core config command."""
    data = dict(msg)
    data.pop("id")
    data.pop("type")

    update_units = data.pop("update_units", False)

    try:
        await hass.config.async_update(**data)
        if update_units:
            async_update_suggested_units(hass)
        connection.send_result(msg["id"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_info", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({"type": "config/core/detect"})
@websocket_api.async_response
async def websocket_detect_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Detect core config."""
    session = async_get_clientsession(hass)
    location_info = await location.async_detect_location_info(session)

    info: dict[str, Any] = {}

    if location_info is None:
        connection.send_result(msg["id"], info)
        return

    # We don't want any integrations to use the name of the unit system
    # so we are using the private attribute here
    if location_info.use_metric:
        # pylint: disable-next=protected-access
        info["unit_system"] = unit_system._CONF_UNIT_SYSTEM_METRIC
    else:
        # pylint: disable-next=protected-access
        info["unit_system"] = unit_system._CONF_UNIT_SYSTEM_US_CUSTOMARY

    if location_info.latitude:
        info["latitude"] = location_info.latitude

    if location_info.longitude:
        info["longitude"] = location_info.longitude

    if location_info.time_zone:
        info["time_zone"] = location_info.time_zone

    if location_info.currency:
        info["currency"] = location_info.currency

    if location_info.country_code:
        info["country"] = location_info.country_code

    connection.send_result(msg["id"], info)
