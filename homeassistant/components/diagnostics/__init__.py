"""The Diagnostics integration."""
from __future__ import annotations

from http import HTTPStatus
import json
import logging
from typing import Any, Protocol

from aiohttp import web
import voluptuous as vol

from homeassistant.components import http, websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import integration_platform
from homeassistant.helpers.device_registry import DeviceEntry, async_get
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.helpers.system_info import async_get_system_info
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_custom_components, async_get_integration
from homeassistant.util.json import (
    find_paths_unserializable_data,
    format_unserializable_data,
)

from .const import DOMAIN, REDACTED, DiagnosticsSubType, DiagnosticsType
from .util import async_redact_data

__all__ = ["REDACTED", "async_redact_data"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Diagnostics from a config entry."""
    hass.data[DOMAIN] = {}

    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _register_diagnostics_platform
    )

    websocket_api.async_register_command(hass, handle_info)
    websocket_api.async_register_command(hass, handle_get)
    hass.http.register_view(DownloadDiagnosticsView)

    return True


class DiagnosticsProtocol(Protocol):
    """Define the format that diagnostics platforms can have."""

    async def async_get_config_entry_diagnostics(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> Any:
        """Return diagnostics for a config entry."""

    async def async_get_device_diagnostics(
        self, hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
    ) -> Any:
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


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "diagnostics/get",
        vol.Required("domain"): str,
    }
)
@callback
def handle_get(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
):
    """List all possible diagnostic handlers."""
    domain = msg["domain"]

    if (info := hass.data[DOMAIN].get(domain)) is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Domain not supported"
        )
        return

    connection.send_result(
        msg["id"],
        {
            "domain": domain,
            "handlers": {key: val is not None for key, val in info.items()},
        },
    )


async def _async_get_json_file_response(
    hass: HomeAssistant,
    data: Any,
    filename: str,
    domain: str,
    d_type: DiagnosticsType,
    d_id: str,
    sub_type: DiagnosticsSubType | None = None,
    sub_id: str | None = None,
) -> web.Response:
    """Return JSON file from dictionary."""
    hass_sys_info = await async_get_system_info(hass)
    hass_sys_info["run_as_root"] = hass_sys_info["user"] == "root"
    del hass_sys_info["user"]

    integration = await async_get_integration(hass, domain)
    custom_components = {}
    all_custom_components = await async_get_custom_components(hass)
    for cc_domain, cc_obj in all_custom_components.items():
        custom_components[cc_domain] = {
            "version": cc_obj.version,
            "requirements": cc_obj.requirements,
        }
    try:
        json_data = json.dumps(
            {
                "home_assistant": hass_sys_info,
                "custom_components": custom_components,
                "integration_manifest": integration.manifest,
                "data": data,
            },
            indent=2,
            cls=ExtendedJSONEncoder,
        )
    except TypeError:
        _LOGGER.error(
            "Failed to serialize to JSON: %s/%s%s. Bad data at %s",
            d_type.value,
            d_id,
            f"/{sub_type.value}/{sub_id}" if sub_type is not None else "",
            format_unserializable_data(find_paths_unserializable_data(data)),
        )
        return web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)

    return web.Response(
        body=json_data,
        content_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}.json.txt"'},
    )


class DownloadDiagnosticsView(http.HomeAssistantView):
    """Download diagnostics view."""

    url = "/api/diagnostics/{d_type}/{d_id}"
    extra_urls = ["/api/diagnostics/{d_type}/{d_id}/{sub_type}/{sub_id}"]
    name = "api:diagnostics"

    async def get(
        self,
        request: web.Request,
        d_type: str,
        d_id: str,
        sub_type: str | None = None,
        sub_id: str | None = None,
    ) -> web.Response:
        """Download diagnostics."""
        # t_type handling
        try:
            d_type = DiagnosticsType(d_type)
        except ValueError:
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        hass = request.app["hass"]

        if (config_entry := hass.config_entries.async_get_entry(d_id)) is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        if (info := hass.data[DOMAIN].get(config_entry.domain)) is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        filename = f"{config_entry.domain}-{config_entry.entry_id}"

        if sub_type is None:
            if info[d_type.value] is None:
                return web.Response(status=HTTPStatus.NOT_FOUND)
            data = await info[d_type.value](hass, config_entry)
            filename = f"{d_type}-{filename}"
            return await _async_get_json_file_response(
                hass, data, filename, config_entry.domain, d_type.value, d_id
            )

        # sub_type handling
        try:
            sub_type = DiagnosticsSubType(sub_type)
        except ValueError:
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        dev_reg = async_get(hass)
        assert sub_id

        if (device := dev_reg.async_get(sub_id)) is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        filename += f"-{device.name}-{device.id}"

        if info[sub_type.value] is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        data = await info[sub_type.value](hass, config_entry, device)
        return await _async_get_json_file_response(
            hass, data, filename, config_entry.domain, d_type, d_id, sub_type, sub_id
        )
