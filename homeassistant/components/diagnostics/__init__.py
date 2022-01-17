"""The Diagnostics integration."""
from __future__ import annotations

import json
import logging

from aiohttp import web
import voluptuous as vol

from homeassistant.components import http, websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import integration_platform
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.util.json import (
    find_paths_unserializable_data,
    format_unserializable_data,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Diagnostics from a config entry."""
    hass.data[DOMAIN] = {}

    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _register_diagnostics_platform
    )

    websocket_api.async_register_command(hass, handle_info)
    hass.http.register_view(DownloadDiagnosticsView)

    return True


async def _register_diagnostics_platform(hass, integration_domain, platform):
    """Register a diagnostics platform."""
    hass.data[DOMAIN][integration_domain] = {
        "config_entry": getattr(platform, "async_get_config_entry_diagnostics", None)
    }


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "diagnostics/list"})
def handle_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
):
    """List all possible diagnostic handlers."""
    connection.send_result(
        msg["id"],
        [
            {
                "domain": domain,
                "handlers": {key: val is not None for key, val in info.items()},
            }
            for domain, info in hass.data[DOMAIN].items()
        ],
    )


class DownloadDiagnosticsView(http.HomeAssistantView):
    """Base CameraView."""

    url = "/api/diagnostics/{type}/{id}"
    name = "api:diagnostics"

    async def get(self, request: web.Request, type: str, id: str) -> web.Response:
        """Download diagnostics."""
        if type != "config_entry":
            return web.Response(status=404)

        hass = request.app["hass"]
        config_entry = hass.config_entries.async_get_entry(id)

        if config_entry is None:
            return web.Response(status=404)

        info = hass.data[DOMAIN].get(config_entry.domain)

        if info is None:
            return web.Response(status=404)

        if info["config_entry"] is None:
            return web.Response(status=404)

        data = await info["config_entry"](hass, config_entry)

        try:
            json_data = json.dumps(data, indent=4, cls=ExtendedJSONEncoder)
        except TypeError:
            _LOGGER.error(
                "Failed to serialize to JSON: %s/%s. Bad data at %s",
                type,
                id,
                format_unserializable_data(find_paths_unserializable_data(data)),
            )
            return web.Response(status=500)

        return web.Response(
            body=json_data,
            content_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{config_entry.domain}-{config_entry.entry_id}.json"'
            },
        )
