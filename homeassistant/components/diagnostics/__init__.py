"""The Diagnostics integration."""
from __future__ import annotations

from http import HTTPStatus
import json
import logging
from typing import Protocol

from aiohttp import web
import voluptuous as vol

from homeassistant.components import http, websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import integration_platform
from homeassistant.helpers.device_registry import DeviceEntry, async_get
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.util.json import (
    find_paths_unserializable_data,
    format_unserializable_data,
)

from .const import DOMAIN, DiagnosticsSubType, DiagnosticsType

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


class DiagnosticsProtocol(Protocol):
    """Define the format that diagnostics platforms can have."""

    async def async_get_config_entry_diagnostics(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> dict:
        """Return diagnostics for a config entry."""

    async def async_get_device_diagnostics(
        self, hass: HomeAssistant, device: DeviceEntry
    ) -> dict:
        """Return diagnostics for a device."""


async def _register_diagnostics_platform(
    hass: HomeAssistant, integration_domain: str, platform: DiagnosticsProtocol
):
    """Register a diagnostics platform."""
    hass.data[DOMAIN][integration_domain] = {
        DiagnosticsType.CONFIG_ENTRY.value: getattr(
            platform, "async_get_config_entry_diagnostics", None
        ),
        DiagnosticsSubType.DEVICE.value: getattr(
            platform, "async_get_device_diagnostics", None
        ),
    }


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "diagnostics/list"})
@callback
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
    """Download diagnostics view."""

    url = "/api/diagnostics/{d_type}/{d_id}"
    extra_urls = ["/api/diagnostics/{d_type}/{d_id}/{sub_type}/{sub_id}"]
    name = "api:diagnostics"

    async def get(  # pylint: disable=no-self-use
        self,
        request: web.Request,
        d_type: str,
        d_id: str,
        sub_type: str | None = None,
        sub_id: str | None = None,
    ) -> web.Response:
        """Download diagnostics."""
        try:
            d_type = DiagnosticsType(d_type)
        except ValueError:
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        hass = request.app["hass"]
        config_entry = hass.config_entries.async_get_entry(d_id)

        if config_entry is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        info = hass.data[DOMAIN].get(config_entry.domain)

        if info is None or info[d_type.value] is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        filename = f"{config_entry.domain}-{config_entry.entry_id}"

        if sub_type is None:
            filename = f"{d_type}-{filename}"
            data = await info[d_type.value](hass, config_entry)
        else:
            try:
                sub_type = DiagnosticsSubType(sub_type)
            except ValueError:
                return web.Response(status=HTTPStatus.BAD_REQUEST)

            dev_reg = async_get(hass)
            assert sub_id
            device = dev_reg.async_get(sub_id)

            if device is None:
                return web.Response(status=HTTPStatus.NOT_FOUND)

            filename += f"-{device.name}-{device.id}"

            if info[sub_type.value] is None:
                return web.Response(status=HTTPStatus.NOT_FOUND)

            data = await info[sub_type.value](hass, config_entry, sub_id)

        try:
            json_data = json.dumps(data, indent=2, cls=ExtendedJSONEncoder)
        except TypeError:
            _LOGGER.error(
                "Failed to serialize to JSON: %s/%s. Bad data at %s",
                d_type,
                d_id,
                format_unserializable_data(find_paths_unserializable_data(data)),
            )
            return web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)

        return web.Response(
            body=json_data,
            content_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
        )
