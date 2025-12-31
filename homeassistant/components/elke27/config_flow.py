"""Config flow for the Elke27 integration."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import asdict, is_dataclass
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv

from elke27_lib.client import Elke27Client

from .const import (
    CONF_LINK_KEYS,
    CONF_PANEL,
    DEFAULT_PORT,
    DOMAIN,
    READY_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE = "device"
CONF_PANEL_INFO = "panel_info"
CONF_TABLE_INFO = "table_info"

MANUAL_ENTRY = "manual_entry"

DISCOVERY_TIMEOUT = 5

STEP_MANUAL_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Optional(CONF_LINK_KEYS, default=""): cv.string,
    }
)

STEP_LINK_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LINK_KEYS, default=""): cv.string,
    }
)


class Elke27ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elke27."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovered_panels: dict[str, Any] = {}
        self._selected_panel: Any | None = None
        self._selected_host: str | None = None
        self._selected_port: int | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            selection = user_input[CONF_DEVICE]
            if selection == MANUAL_ENTRY:
                return await self.async_step_manual()

            panel = self._discovered_panels[selection]
            panel_dict = _panel_to_dict(panel)
            panel_mac = panel_dict.get("panel_mac")
            host = panel_dict.get("panel_host")
            port = panel_dict.get("port", DEFAULT_PORT)

            if panel_mac:
                await self.async_set_unique_id(panel_mac)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: host, CONF_PORT: port}
                )

            self._selected_panel = panel
            self._selected_host = host
            self._selected_port = port
            return await self.async_step_link()

        panels = await self._async_discover()
        if panels:
            self._discovered_panels = panels
            options = {
                panel_id: _panel_label(_panel_to_dict(panel))
                for panel_id, panel in panels.items()
            }
            options[MANUAL_ENTRY] = "Manual entry"
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(options)}),
            )

        return await self.async_step_manual()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual host/port entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            link_keys = _parse_link_keys(user_input.get(CONF_LINK_KEYS, ""))
            if link_keys is _INVALID_LINK_KEYS:
                errors["base"] = "invalid_link_keys"
            else:
                self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})
                return await self._async_create_entry(
                    host=host,
                    port=port,
                    link_keys=link_keys,
                    panel=None,
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle optional link keys after discovery selection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            link_keys = _parse_link_keys(user_input.get(CONF_LINK_KEYS, ""))
            if link_keys is _INVALID_LINK_KEYS:
                errors["base"] = "invalid_link_keys"
            else:
                return await self._async_create_entry(
                    host=self._selected_host,
                    port=self._selected_port,
                    link_keys=link_keys,
                    panel=self._selected_panel,
                )

        return self.async_show_form(
            step_id="link",
            data_schema=STEP_LINK_DATA_SCHEMA,
            errors=errors,
        )

    async def _async_create_entry(
        self, host: str, port: int, link_keys: Any, panel: Any | None
    ) -> ConfigFlowResult:
        """Connect, fetch snapshots, and create the entry."""
        errors: dict[str, str] = {}
        panel_info, table_info, error = await _async_connect_and_fetch(
            host, port, link_keys, panel
        )
        if error:
            errors["base"] = error
            return self.async_show_form(
                step_id="manual" if panel is None else "link",
                data_schema=STEP_MANUAL_DATA_SCHEMA if panel is None else STEP_LINK_DATA_SCHEMA,
                errors=errors,
            )

        data: dict[str, Any] = {CONF_HOST: host, CONF_PORT: port}
        if link_keys is not None:
            data[CONF_LINK_KEYS] = link_keys
        if panel is not None:
            data[CONF_PANEL] = _panel_to_dict(panel)

        options: dict[str, Any] = {
            CONF_PANEL_INFO: panel_info,
            CONF_TABLE_INFO: table_info,
        }

        title = panel_info.get("panel_name") if panel_info else host
        return self.async_create_entry(title=title, data=data, options=options)

    async def _async_discover(self) -> dict[str, Any]:
        """Discover panels via the client."""
        try:
            client = Elke27Client("0.0.0.0", DEFAULT_PORT)
            result = await client.discover(timeout=DISCOVERY_TIMEOUT)
        except Exception as err:
            _LOGGER.debug("Discovery failed: %s", err)
            return {}

        if not result.ok or result.data is None:
            if result.error:
                _LOGGER.debug("Discovery error: %s", result.error)
            return {}

        panels: dict[str, Any] = {}
        for panel in result.data.panels:
            panel_dict = _panel_to_dict(panel)
            panel_id = panel_dict.get("panel_mac") or panel_dict.get("panel_host")
            if panel_id:
                panels[panel_id] = panel
        return panels


_INVALID_LINK_KEYS = object()


def _parse_link_keys(raw: str) -> Any:
    """Parse link keys from a JSON string."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _INVALID_LINK_KEYS


def _panel_to_dict(panel: Any) -> dict[str, Any]:
    """Normalize a discovered panel entry into a dict."""
    if panel is None:
        return {}
    if is_dataclass(panel):
        return asdict(panel)
    if isinstance(panel, dict):
        return dict(panel)
    return {
        key: getattr(panel, key, None)
        for key in (
            "panel_mac",
            "panel_name",
            "panel_serial",
            "panel_host",
            "port",
            "tls_port",
        )
        if getattr(panel, key, None) is not None
    }


def _panel_label(panel: dict[str, Any]) -> str:
    """Build a display label for a panel."""
    name = panel.get("panel_name") or "Elke27 panel"
    host = panel.get("panel_host") or panel.get("host")
    port = panel.get("port")
    if host:
        if port:
            return f"{name} ({host}:{port})"
        return f"{name} ({host})"
    return name


async def _async_connect_and_fetch(
    host: str,
    port: int,
    link_keys: Any,
    panel: Any | None,
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    """Connect to the panel and return snapshots."""
    client = Elke27Client(host, port)
    try:
        result = await client.connect(link_keys, panel=panel)
        if not result.ok:
            return {}, {}, _map_error(result.error)

        ready = await asyncio.to_thread(client.wait_ready, timeout_s=READY_TIMEOUT)
        if not ready:
            return {}, {}, "cannot_connect"

        panel_info = _snapshot_to_dict(
            client.panel_info,
            [
                "panel_name",
                "panel_mac",
                "panel_serial",
                "panel_host",
                "port",
                "tls_port",
                "session_id",
            ],
        )
        table_info = _snapshot_to_dict(
            client.table_info,
            [
                "areas",
                "zones",
                "outputs",
                "lights",
                "thermostats",
            ],
        )
        return panel_info, table_info, None
    except Exception as err:
        _LOGGER.debug("Connection setup failed: %s", err)
        return {}, {}, "cannot_connect"
    finally:
        with contextlib.suppress(Exception):
            await client.disconnect()


def _snapshot_to_dict(snapshot: Any, field_names: list[str]) -> dict[str, Any]:
    """Serialize a snapshot to a dict."""
    if snapshot is None:
        return {}
    if is_dataclass(snapshot):
        return asdict(snapshot)
    if isinstance(snapshot, dict):
        return dict(snapshot)
    data = {name: getattr(snapshot, name, None) for name in field_names}
    return {key: value for key, value in data.items() if value is not None}


def _map_error(error: Any) -> str:
    """Map client errors to config flow error keys."""
    if error is None:
        return "cannot_connect"
    name = error.__class__.__name__
    return {
        "InvalidLinkKeys": "invalid_link_keys",
        "InvalidCredentials": "invalid_auth",
        "AuthorizationRequired": "authorization_required",
        "MissingContext": "missing_context",
        "ConnectionLost": "cannot_connect",
        "ProtocolError": "cannot_connect",
        "CryptoError": "cannot_connect",
    }.get(name, "cannot_connect")
