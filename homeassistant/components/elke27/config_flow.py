"""Config flow for the Elke27 integration."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import logging
from typing import Any

import voluptuous as vol

from elke27_lib import ClientConfig, DiscoveredPanel, Elke27Client
from elke27_lib.errors import (
    Elke27AuthError,
    Elke27ConnectionError,
    Elke27DisconnectedError,
    Elke27Error,
    Elke27LinkRequiredError,
    Elke27TimeoutError,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import selector

from .const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS_JSON,
    CONF_PANEL,
    DEFAULT_PORT,
    DOMAIN,
    READY_TIMEOUT,
)
from .identity import async_get_integration_serial

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE = "device"
CONF_ACCESS_CODE = "access_code"
CONF_PASSPHRASE = "passphrase"
CONF_PANEL_INFO = "panel_info"
CONF_TABLE_INFO = "table_info"

MANUAL_ENTRY = "manual_entry"

DISCOVERY_TIMEOUT = 5

STEP_MANUAL_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

STEP_LINK_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_CODE): cv.string,
        vol.Required(CONF_PASSPHRASE): selector({"text": {"type": "password"}}),
    }
)


class Elke27ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elke27."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovered_panels: dict[str, DiscoveredPanel] = {}
        self._selected_panel: DiscoveredPanel | None = None
        self._selected_host: str | None = None
        self._selected_port: int | None = None
        self._reauth_entry: Any | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            selection = user_input[CONF_DEVICE]
            if selection == MANUAL_ENTRY:
                return await self.async_step_manual()

            panel = self._discovered_panels.get(selection)
            if panel is None:
                return await self.async_step_manual()

            panel_info = _panel_to_dict(panel)
            self._selected_host = _panel_host(panel_info)
            self._selected_port = _panel_port(panel_info)
            self._selected_panel = panel
            if not self._selected_host:
                return await self.async_step_manual()
            self._async_abort_entries_match(
                {CONF_HOST: self._selected_host, CONF_PORT: self._selected_port}
            )
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
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            self._selected_host = host
            self._selected_port = port
            self._selected_panel = None
            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})
            return await self.async_step_link()

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle access code and passphrase entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            access_code = user_input[CONF_ACCESS_CODE]
            passphrase = user_input[CONF_PASSPHRASE]
            return await self._async_link_and_create_entry(
                access_code=access_code,
                passphrase=passphrase,
                errors=errors,
                step_id="link",
            )

        return self.async_show_form(
            step_id="link",
            data_schema=STEP_LINK_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth for missing or invalid link keys."""
        entry_id = self.context.get("entry_id")
        self._reauth_entry = (
            self.hass.config_entries.async_get_entry(entry_id)
            if entry_id is not None
            else None
        )
        return await self.async_step_relink(user_input)

    async def async_step_relink(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Relink using access code and passphrase."""
        errors: dict[str, str] = {}
        if user_input is not None:
            entry = self._reauth_entry
            if entry is None:
                return self.async_abort(reason="missing_context")

            access_code = user_input[CONF_ACCESS_CODE]
            passphrase = user_input[CONF_PASSPHRASE]
            self._selected_host = entry.data.get(CONF_HOST)
            self._selected_port = entry.data.get(CONF_PORT)
            self._selected_panel = entry.data.get(CONF_PANEL)
            return await self._async_link_and_create_entry(
                access_code=access_code,
                passphrase=passphrase,
                errors=errors,
                step_id="relink",
                entry=entry,
            )

        return self.async_show_form(
            step_id="relink",
            data_schema=STEP_LINK_DATA_SCHEMA,
            errors=errors,
        )

    async def _async_link_and_create_entry(
        self,
        access_code: str,
        passphrase: str,
        errors: dict[str, str],
        step_id: str,
        entry: Any | None = None,
    ) -> ConfigFlowResult:
        """Link, connect, fetch snapshots, and create/update the entry."""
        host = self._selected_host
        port = self._selected_port
        if host is None or port is None:
            errors["base"] = "unknown"
            return self.async_show_form(
                step_id=step_id,
                data_schema=STEP_LINK_DATA_SCHEMA,
                errors=errors,
            )

        integration_serial = await async_get_integration_serial(
            self.hass,
            host,
            entry.data.get(CONF_INTEGRATION_SERIAL) if entry is not None else None,
        )
        client = _create_client()
        try:
            link_keys = await client.async_link(
                host=host,
                port=port,
                access_code=access_code,
                passphrase=passphrase,
            )
            await client.async_connect(host=host, port=port, link_keys=link_keys)
            ready = await client.wait_ready(timeout_s=READY_TIMEOUT)
            if not ready:
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id=step_id,
                    data_schema=STEP_LINK_DATA_SCHEMA,
                    errors=errors,
                )

            snapshot = client.snapshot
            panel_info = _snapshot_to_dict(getattr(snapshot, "panel_info", None))
            table_info = _snapshot_to_dict(getattr(snapshot, "table_info", None))
        except Elke27AuthError:
            errors["base"] = "invalid_auth"
        except (Elke27ConnectionError, Elke27TimeoutError, Elke27DisconnectedError):
            errors["base"] = "cannot_connect"
        except Elke27LinkRequiredError:
            errors["base"] = "link_required"
        except Elke27Error:
            errors["base"] = "unknown"
        else:
            link_keys_json = link_keys.to_json()
            data: dict[str, Any] = {
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_LINK_KEYS_JSON: link_keys_json,
                CONF_INTEGRATION_SERIAL: integration_serial,
            }

            panel = self._selected_panel
            if panel is not None:
                data[CONF_PANEL] = _panel_to_dict(panel)

            options: dict[str, Any] = {
                CONF_PANEL_INFO: panel_info,
                CONF_TABLE_INFO: table_info,
            }

            unique_id = _panel_mac(panel_info) or integration_serial
            if unique_id:
                await self.async_set_unique_id(unique_id)
                if entry is None:
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: host, CONF_PORT: port}
                    )

            title = _panel_name(panel_info) or host
            if entry is not None:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, **data},
                    options={**entry.options, **options},
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            result = self.async_create_entry(title=title, data=data, options=options)
            if "title" not in result:
                result["title"] = title
            return result

        return self.async_show_form(
            step_id=step_id,
            data_schema=STEP_LINK_DATA_SCHEMA,
            errors=errors,
        )

    async def _async_discover(self) -> dict[str, DiscoveredPanel]:
        """Discover panels via the client."""
        client = _create_client()
        try:
            panels = await client.async_discover(timeout_s=DISCOVERY_TIMEOUT)
        except Elke27Error as err:
            _LOGGER.debug("Discovery failed: %s", err)
            return {}

        discovered: dict[str, DiscoveredPanel] = {}
        for panel in panels or []:
            panel_id = _panel_id(panel)
            if panel_id:
                discovered[panel_id] = panel
        return discovered


def _create_client() -> Elke27Client:
    """Create a configured client instance."""
    return Elke27Client(ClientConfig())


def _panel_id(panel: DiscoveredPanel) -> str | None:
    panel_dict = _panel_to_dict(panel)
    return panel_dict.get("mac") or panel_dict.get("host")


def _panel_to_dict(panel: DiscoveredPanel | dict[str, Any] | None) -> dict[str, Any]:
    """Normalize a discovered panel entry into a dict."""
    if panel is None:
        return {}
    if is_dataclass(panel):
        return _normalize_panel_keys(asdict(panel))
    if isinstance(panel, dict):
        return _normalize_panel_keys(dict(panel))
    return _normalize_panel_keys(
        {
            key: getattr(panel, key, None)
            for key in ("host", "port", "name", "model", "mac")
            if getattr(panel, key, None) is not None
        }
    )


def _normalize_panel_keys(panel: dict[str, Any]) -> dict[str, Any]:
    """Normalize discovery panel keys to the expected schema."""
    normalized = dict(panel)
    if "host" not in normalized and "ip" in normalized:
        normalized["host"] = normalized.get("ip")
    if "name" not in normalized and "panel_name" in normalized:
        normalized["name"] = normalized.get("panel_name")
    if "mac" not in normalized and "panel_mac" in normalized:
        normalized["mac"] = normalized.get("panel_mac")
    if "model" not in normalized and "panel_model" in normalized:
        normalized["model"] = normalized.get("panel_model")
    return normalized


def _panel_label(panel: dict[str, Any]) -> str:
    """Build a display label for a panel."""
    host = panel.get("host")
    port = panel.get("port")
    host_label = f"{host}:{port}" if host and port else host or "Unknown host"
    extras = [
        value
        for value in (panel.get("name"), panel.get("model"), panel.get("mac"))
        if value
    ]
    if extras:
        return f"{host_label} ({' - '.join(extras)})"
    return host_label


def _panel_host(panel: dict[str, Any]) -> str | None:
    return panel.get("host")


def _panel_port(panel: dict[str, Any]) -> int:
    return int(panel.get("port") or DEFAULT_PORT)


def _panel_mac(panel_info: dict[str, Any]) -> str | None:
    return panel_info.get("mac") or panel_info.get("panel_mac")


def _panel_name(panel_info: dict[str, Any]) -> str | None:
    return panel_info.get("panel_name") or panel_info.get("name")


def _snapshot_to_dict(snapshot: Any) -> dict[str, Any]:
    """Serialize a snapshot to a dict."""
    if snapshot is None:
        return {}
    if is_dataclass(snapshot):
        return asdict(snapshot)
    if isinstance(snapshot, dict):
        return dict(snapshot)
    return {
        key: value
        for key, value in snapshot.__dict__.items()
        if not key.startswith("_")
    }
