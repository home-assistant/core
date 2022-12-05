"""The Diagnostics integration."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import asdict as dataclass_asdict, dataclass
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


@dataclass
class DiagnosticsSubscriptionSupport:
    """Describe subscriptions supported by the platform."""

    config_entry: bool
    domain: bool


@dataclass
class DiagnosticsPlatformData:
    """Diagnostic platform data."""

    config_entry_diagnostics: Callable[
        [HomeAssistant, ConfigEntry], Coroutine[Any, Any, Any]
    ] | None
    device_diagnostics: Callable[
        [HomeAssistant, ConfigEntry, DeviceEntry], Coroutine[Any, Any, Any]
    ] | None
    subscription_support: DiagnosticsSubscriptionSupport


class DiagnosticsData:
    """Diagnostic data."""

    def __init__(self) -> None:
        """Initialize diagnostic data."""
        self.platforms: dict[str, DiagnosticsPlatformData] = {}
        self.domain_subscriptions: defaultdict[
            str, set[tuple[websocket_api.ActiveConnection, int]]
        ] = defaultdict(set)
        self.config_entry_subscriptions: defaultdict[
            str, set[tuple[websocket_api.ActiveConnection, int]]
        ] = defaultdict(set)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Diagnostics from a config entry."""
    hass.data[DOMAIN] = DiagnosticsData()

    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _register_diagnostics_platform
    )

    websocket_api.async_register_command(hass, handle_info)
    websocket_api.async_register_command(hass, handle_get)
    websocket_api.async_register_command(hass, handle_subscribe_diagnostics)
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

    @callback
    def async_supports_subscription(self) -> DiagnosticsSubscriptionSupport:
        """Return if the platform supports subscribing to diagnostics."""


async def _register_diagnostics_platform(
    hass: HomeAssistant, integration_domain: str, platform: DiagnosticsProtocol
) -> None:
    """Register a diagnostics platform."""
    diagnostics_data: DiagnosticsData = hass.data[DOMAIN]
    subscription_support: DiagnosticsSubscriptionSupport
    if hasattr(platform, "async_supports_subscription"):
        subscription_support = platform.async_supports_subscription()
    else:
        subscription_support = DiagnosticsSubscriptionSupport(False, False)

    diagnostics_data.platforms[integration_domain] = DiagnosticsPlatformData(
        getattr(platform, "async_get_config_entry_diagnostics", None),
        getattr(platform, "async_get_device_diagnostics", None),
        subscription_support,
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
            "supports_subscription": dataclass_asdict(info.subscription_support),
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
            "supports_subscription": dataclass_asdict(info.subscription_support),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "diagnostics/subscribe",
        vol.Required("domain"): str,
        vol.Optional("config_entry"): str,
    }
)
@callback
def handle_subscribe_diagnostics(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Subscribe to diagnostic messages."""

    diagnostics_data: DiagnosticsData = hass.data[DOMAIN]

    msg_id = msg["id"]
    domain = msg["domain"]
    config_entry = msg.get("config_entry")
    diagnostics_data.domain_subscriptions[domain].add((connection, msg_id))
    if config_entry:
        diagnostics_data.config_entry_subscriptions[config_entry].add(
            (connection, msg_id)
        )

    @callback
    def cancel_subscription() -> None:
        diagnostics_data.domain_subscriptions[domain].remove((connection, msg["id"]))
        if config_entry:
            diagnostics_data.config_entry_subscriptions[config_entry].remove(
                (connection, msg_id)
            )

    connection.subscriptions[msg["id"]] = cancel_subscription

    connection.send_message(websocket_api.result_message(msg["id"]))


async def _async_get_json_file_response(
    hass: HomeAssistant,
    data: Any,
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

        hass: HomeAssistant = request.app["hass"]

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


@callback
def async_has_subscription(
    hass: HomeAssistant, domain: str, config_entry_id: str | None = None
) -> bool:
    """Return True if there is a matching diagnostics subscription."""

    diagnostics_data: DiagnosticsData = hass.data[DOMAIN]
    if (
        domain in diagnostics_data.domain_subscriptions
        and diagnostics_data.domain_subscriptions[domain]
    ):
        return True

    if not config_entry_id:
        return False

    if (
        config_entry_id in diagnostics_data.config_entry_subscriptions
        and diagnostics_data.config_entry_subscriptions[config_entry_id]
    ):
        return True

    return False


@callback
def async_log_object(
    hass: HomeAssistant,
    data: Any,
    domain: str,
    config_entry_id: str | None = None,
) -> None:
    """Send diagnostic data to subscribers."""
    diagnostics_data: DiagnosticsData = hass.data[DOMAIN]

    json_data = json.dumps({"data": data}, cls=ExtendedJSONEncoder)

    domain_subs: set[tuple[websocket_api.ActiveConnection, int]] = set()

    if domain in diagnostics_data.domain_subscriptions:
        for conn, msg_id in diagnostics_data.domain_subscriptions[domain]:
            conn.send_message(websocket_api.event_message(msg_id, json_data))
            domain_subs.add((conn, msg_id))

    if not config_entry_id:
        return

    if (
        config_entry_id in diagnostics_data.config_entry_subscriptions
        and diagnostics_data.config_entry_subscriptions[config_entry_id]
    ):
        for conn, msg_id in diagnostics_data.config_entry_subscriptions[
            config_entry_id
        ]:
            if (conn, msg_id) in domain_subs:
                continue
            conn.send_message(websocket_api.event_message(msg_id, json_data))
