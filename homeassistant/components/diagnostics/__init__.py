"""The Diagnostics integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
from dataclasses import dataclass, field
from http import HTTPStatus
import json
import logging
from typing import Any, Protocol

from aiohttp import web
import voluptuous as vol

from homeassistant.components import http, websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, integration_platform
from homeassistant.helpers.device_registry import DeviceEntry, async_get
from homeassistant.helpers.json import (
    ExtendedJSONEncoder,
    find_paths_unserializable_data,
)
from homeassistant.helpers.system_info import async_get_system_info
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_custom_components, async_get_integration
from homeassistant.util.json import format_unserializable_data

from .const import DOMAIN, REDACTED, DiagnosticsSubType, DiagnosticsType
from .util import async_redact_data

__all__ = ["REDACTED", "async_redact_data"]

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@dataclass(slots=True)
class DiagnosticsPlatformData:
    """Diagnostic platform data."""

    config_entry_diagnostics: (
        Callable[[HomeAssistant, ConfigEntry], Coroutine[Any, Any, Mapping[str, Any]]]
        | None
    )
    device_diagnostics: (
        Callable[
            [HomeAssistant, ConfigEntry, DeviceEntry],
            Coroutine[Any, Any, Mapping[str, Any]],
        ]
        | None
    )


@dataclass(slots=True)
class DiagnosticsData:
    """Diagnostic data."""

    platforms: dict[str, DiagnosticsPlatformData] = field(default_factory=dict)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Diagnostics from a config entry."""
    hass.data[DOMAIN] = DiagnosticsData()

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
    ) -> Mapping[str, Any]:
        """Return diagnostics for a config entry."""

    async def async_get_device_diagnostics(
        self, hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
    ) -> Mapping[str, Any]:
        """Return diagnostics for a device."""


@callback
def _register_diagnostics_platform(
    hass: HomeAssistant, integration_domain: str, platform: DiagnosticsProtocol
) -> None:
    """Register a diagnostics platform."""
    diagnostics_data: DiagnosticsData = hass.data[DOMAIN]
    diagnostics_data.platforms[integration_domain] = DiagnosticsPlatformData(
        getattr(platform, "async_get_config_entry_diagnostics", None),
        getattr(platform, "async_get_device_diagnostics", None),
    )


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "diagnostics/list"})
@callback
def handle_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """List all possible diagnostic handlers."""
    diagnostics_data: DiagnosticsData = hass.data[DOMAIN]
    result = [
        {
            "domain": domain,
            "handlers": {
                DiagnosticsType.CONFIG_ENTRY: info.config_entry_diagnostics is not None,
                DiagnosticsSubType.DEVICE: info.device_diagnostics is not None,
            },
        }
        for domain, info in diagnostics_data.platforms.items()
    ]
    connection.send_result(msg["id"], result)


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
) -> None:
    """List all diagnostic handlers for a domain."""
    domain = msg["domain"]
    diagnostics_data: DiagnosticsData = hass.data[DOMAIN]

    if (info := diagnostics_data.platforms.get(domain)) is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Domain not supported"
        )
        return

    connection.send_result(
        msg["id"],
        {
            "domain": domain,
            "handlers": {
                DiagnosticsType.CONFIG_ENTRY: info.config_entry_diagnostics is not None,
                DiagnosticsSubType.DEVICE: info.device_diagnostics is not None,
            },
        },
    )


async def _async_get_json_file_response(
    hass: HomeAssistant,
    data: Mapping[str, Any],
    filename: str,
    domain: str,
    d_id: str,
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
            "documentation": cc_obj.documentation,
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
            DiagnosticsType.CONFIG_ENTRY.value,
            d_id,
            f"/{DiagnosticsSubType.DEVICE.value}/{sub_id}"
            if sub_id is not None
            else "",
            format_unserializable_data(find_paths_unserializable_data(data)),
        )
        return web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)

    return web.Response(
        body=json_data,
        content_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
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
        # Validate d_type and sub_type
        try:
            DiagnosticsType(d_type)
        except ValueError:
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        if sub_type is not None:
            try:
                DiagnosticsSubType(sub_type)
            except ValueError:
                return web.Response(status=HTTPStatus.BAD_REQUEST)

        device_diagnostics = sub_type is not None

        hass = request.app[http.KEY_HASS]

        if (config_entry := hass.config_entries.async_get_entry(d_id)) is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        diagnostics_data: DiagnosticsData = hass.data[DOMAIN]
        if (info := diagnostics_data.platforms.get(config_entry.domain)) is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        filename = f"{config_entry.domain}-{config_entry.entry_id}"

        if not device_diagnostics:
            # Config entry diagnostics
            if info.config_entry_diagnostics is None:
                return web.Response(status=HTTPStatus.NOT_FOUND)
            data = await info.config_entry_diagnostics(hass, config_entry)
            filename = f"{DiagnosticsType.CONFIG_ENTRY}-{filename}"
            return await _async_get_json_file_response(
                hass, data, filename, config_entry.domain, d_id
            )

        # Device diagnostics
        dev_reg = async_get(hass)
        if sub_id is None:
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        if (device := dev_reg.async_get(sub_id)) is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        filename += f"-{device.name}-{device.id}"

        if info.device_diagnostics is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        data = await info.device_diagnostics(hass, config_entry, device)
        return await _async_get_json_file_response(
            hass, data, filename, config_entry.domain, d_id, sub_id
        )
