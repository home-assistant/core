"""Config flow for the Elke27 integration."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any

from elke27_lib import ClientConfig, LinkKeys
from elke27_lib.client import Elke27Client
from elke27_lib.discovery import AIOELKDiscovery
from elke27_lib.errors import (
    Elke27AuthError,
    Elke27ConnectionError,
    Elke27DisconnectedError,
    Elke27Error,
    Elke27LinkRequiredError,
    Elke27TimeoutError,
    InvalidCredentials,
)
import voluptuous as vol

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
from .identity import async_get_integration_serial, build_client_identity

if TYPE_CHECKING:
    from collections.abc import Mapping

CONF_ACCESS_CODE = "access_code"
CONF_PASSPHRASE = "passphrase"
CONF_PANEL_INFO = "panel_info"
CONF_TABLE_INFO = "table_info"
CONF_RESCAN = "__rescan__"
CONF_SETUP_METHOD = "setup_method"
SETUP_METHOD_DISCOVER = "discover"
SETUP_METHOD_MANUAL = "manual"

STEP_MANUAL_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_ACCESS_CODE): selector({"text": {"type": "password"}}),
        vol.Required(CONF_PASSPHRASE): selector({"text": {"type": "password"}}),
    }
)

STEP_LINK_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_CODE): selector({"text": {"type": "password"}}),
        vol.Required(CONF_PASSPHRASE): selector({"text": {"type": "password"}}),
    }
)

STEP_REAUTH_DATA_SCHEMA = STEP_LINK_DATA_SCHEMA

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SETUP_METHOD, default=SETUP_METHOD_DISCOVER): selector(
            {
                "select": {
                    "options": [
                        {
                            "value": SETUP_METHOD_DISCOVER,
                            "label": "Discover panels",
                        },
                        {"value": SETUP_METHOD_MANUAL, "label": "Manual setup"},
                    ],
                    "mode": "list",
                }
            }
        )
    }
)


class Elke27ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elke27."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._selected_panel: Any | None = None
        self._selected_host: str | None = None
        self._selected_port: int | None = None
        self._reauth_entry: Any | None = None
        self._discovered_panels: list[Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            if user_input[CONF_SETUP_METHOD] == SETUP_METHOD_MANUAL:
                return await self.async_step_manual()
            return await self.async_step_discover()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = DEFAULT_PORT
            self._selected_host = host
            self._selected_port = port
            self._selected_panel = None
            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})
            return await self._async_link_and_create_entry(
                access_code=user_input[CONF_ACCESS_CODE],
                passphrase=user_input[CONF_PASSPHRASE],
                errors=errors,
                step_id="manual",
                data_schema=STEP_MANUAL_DATA_SCHEMA,
            )

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery-based setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data_schema = self._discovery_schema()
            if CONF_PANEL in user_input:
                panel_idx_raw = user_input[CONF_PANEL]
                if panel_idx_raw == CONF_RESCAN:
                    self._discovered_panels = None
                    return await self.async_step_discover(None)
                panel_idx = int(panel_idx_raw)
                if not self._discovered_panels or panel_idx >= len(
                    self._discovered_panels
                ):
                    errors["base"] = "no_panels_found"
                    return self.async_show_form(
                        step_id="discover",
                        data_schema=self._discovery_schema(),
                        errors=errors,
                    )
                panel = self._discovered_panels[panel_idx]
                host = getattr(panel, "panel_host", None) or getattr(
                    panel, "host", None
                )
                port = getattr(panel, "port", None) or DEFAULT_PORT
                if not host:
                    errors["base"] = "no_panels_found"
                    return self.async_show_form(
                        step_id="discover",
                        data_schema=self._discovery_schema(),
                        errors=errors,
                    )
                self._selected_host = host
                self._selected_port = int(port)
                self._selected_panel = panel
            else:
                data_schema = STEP_LINK_DATA_SCHEMA
            if self._selected_panel is None:
                errors["base"] = "no_panels_found"
                return self.async_show_form(
                    step_id="discover",
                    data_schema=data_schema,
                    errors=errors,
                )
            if self._is_panel_configured(self._selected_panel):
                return self.async_abort(reason="already_configured")
            return await self._async_link_and_create_entry(
                access_code=user_input[CONF_ACCESS_CODE],
                passphrase=user_input[CONF_PASSPHRASE],
                errors=errors,
                step_id="discover",
                data_schema=data_schema,
            )

        if self._discovered_panels is None:
            discovery = AIOELKDiscovery()
            self._discovered_panels = self._dedupe_panels(await discovery.async_scan())
        if not self._discovered_panels:
            errors["base"] = "no_panels_found"
        if self._discovered_panels and len(self._discovered_panels) == 1:
            panel = self._discovered_panels[0]
            self._selected_panel = panel
            self._selected_host = getattr(panel, "panel_host", None) or getattr(
                panel, "host", None
            )
            self._selected_port = int(getattr(panel, "port", None) or DEFAULT_PORT)
            return self.async_show_form(
                step_id="discover",
                data_schema=STEP_LINK_DATA_SCHEMA,
                errors=errors,
            )

        return self.async_show_form(
            step_id="discover",
            data_schema=self._discovery_schema(),
            errors=errors,
        )

    async def async_step_reauth(
        self, _entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth for missing or invalid link keys."""
        entry_id = self.context.get("entry_id")
        self._reauth_entry = (
            self.hass.config_entries.async_get_entry(entry_id)
            if entry_id is not None
            else None
        )
        return await self.async_step_relink(None)

    async def async_step_relink(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Relink using access code and passphrase."""
        errors: dict[str, str] = {}
        if (
            user_input is not None
            and CONF_ACCESS_CODE in user_input
            and CONF_PASSPHRASE in user_input
        ):
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
                data_schema=STEP_REAUTH_DATA_SCHEMA,
                entry=entry,
            )

        return self.async_show_form(
            step_id="relink",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )

    async def _async_link_and_create_entry(
        self,
        access_code: str,
        passphrase: str,
        errors: dict[str, str],
        step_id: str,
        data_schema: vol.Schema,
        entry: Any | None = None,
    ) -> ConfigFlowResult:
        """Link, connect, fetch snapshots, and create/update the entry."""
        host = self._selected_host
        port = self._selected_port
        if host is None or port is None:
            errors["base"] = "unknown"
            return self.async_show_form(
                step_id=step_id,
                data_schema=data_schema,
                errors=errors,
            )

        integration_serial = await async_get_integration_serial(
            self.hass,
            host,
            entry.data.get(CONF_INTEGRATION_SERIAL) if entry is not None else None,
        )
        client_identity = build_client_identity(integration_serial)
        client = _create_client()
        link_keys: LinkKeys | None = None
        panel_info: dict[str, Any] = {}
        table_info: dict[str, Any] = {}
        try:
            link_keys = await client.async_link(
                host=host,
                port=port,
                access_code=access_code,
                passphrase=passphrase,
                client_identity=client_identity,
            )
            await client.async_connect(host=host, port=port, link_keys=link_keys)
            ready = await client.wait_ready(timeout_s=READY_TIMEOUT)
            if not ready:
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id=step_id,
                    data_schema=data_schema,
                    errors=errors,
                )

            snapshot = client.snapshot
            panel_info = _snapshot_to_dict(
                getattr(snapshot, "panel_info", None)
                or getattr(snapshot, "panel", None)
            )
            table_info = _snapshot_to_dict(getattr(snapshot, "table_info", None))
        except InvalidCredentials:
            errors["base"] = "invalid_auth"
        except Elke27AuthError:
            errors["base"] = "cannot_connect"
        except (Elke27ConnectionError, Elke27TimeoutError, Elke27DisconnectedError):
            errors["base"] = "cannot_connect"
        except Elke27LinkRequiredError:
            errors["base"] = "link_required"
        except Elke27Error:
            errors["base"] = "unknown"
        finally:
            await client.async_disconnect()

        if errors or link_keys is None:
            return self.async_show_form(
                step_id=step_id,
                data_schema=data_schema,
                errors=errors,
            )

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

    def _discovery_schema(self) -> vol.Schema:
        options = [
            {
                "value": str(idx),
                "label": _panel_label(
                    panel, already_configured=self._is_panel_configured(panel)
                ),
            }
            for idx, panel in enumerate(self._discovered_panels or [])
        ]
        if options:
            options.insert(0, {"value": CONF_RESCAN, "label": "Rescan for panels"})
        else:
            options = [{"value": CONF_RESCAN, "label": "Rescan for panels"}]
        return vol.Schema(
            {
                vol.Required(CONF_PANEL): selector(
                    {"select": {"options": options, "mode": "list"}}
                ),
                vol.Required(CONF_ACCESS_CODE): selector(
                    {"text": {"type": "password"}}
                ),
                vol.Required(CONF_PASSPHRASE): selector({"text": {"type": "password"}}),
            }
        )

    def _dedupe_panels(self, panels: list[Any]) -> list[Any]:
        deduped: list[Any] = []
        seen: set[tuple[str, str]] = set()
        for panel in panels:
            key = self._panel_key(panel)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(panel)
        return deduped

    def _panel_key(self, panel: Any) -> tuple[str, str]:
        mac = getattr(panel, "panel_mac", None) or getattr(panel, "mac", None)
        serial = getattr(panel, "panel_serial", None) or getattr(panel, "serial", None)
        host = getattr(panel, "panel_host", None) or getattr(panel, "host", None)
        port = getattr(panel, "port", None) or DEFAULT_PORT
        if mac:
            return ("mac", str(mac))
        if serial:
            return ("serial", str(serial))
        return ("host", f"{host}:{port}")

    def _is_panel_configured(self, panel: Any) -> bool:
        host = getattr(panel, "panel_host", None) or getattr(panel, "host", None)
        port = getattr(panel, "port", None) or DEFAULT_PORT
        if not host:
            return False
        entries = self.hass.config_entries.async_entries(DOMAIN)
        for entry in entries:
            if entry.data.get(CONF_HOST) == host and entry.data.get(CONF_PORT) == port:
                return True
        return False


def _create_client() -> Elke27Client:
    """Create a configured client instance."""
    return Elke27Client(ClientConfig())


def _panel_to_dict(panel: Any | None) -> dict[str, Any]:
    """Normalize a discovered panel entry into a dict."""
    if panel is None:
        return {}
    if is_dataclass(panel) and not isinstance(panel, type):
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
    if "host" not in normalized and "panel_host" in normalized:
        normalized["host"] = normalized.get("panel_host")
    if "port" not in normalized and "panel_port" in normalized:
        normalized["port"] = normalized.get("panel_port")
    if "name" not in normalized and "panel_name" in normalized:
        normalized["name"] = normalized.get("panel_name")
    if "mac" not in normalized and "panel_mac" in normalized:
        normalized["mac"] = normalized.get("panel_mac")
    if "model" not in normalized and "panel_model" in normalized:
        normalized["model"] = normalized.get("panel_model")
    return normalized


def _panel_mac(panel_info: dict[str, Any]) -> str | None:
    return panel_info.get("mac") or panel_info.get("panel_mac")


def _panel_name(panel_info: dict[str, Any]) -> str | None:
    return (
        panel_info.get("panel_name")
        or panel_info.get("name")
        or panel_info.get("serial")
        or panel_info.get("panel_serial")
    )


def _panel_label(panel: Any, *, already_configured: bool = False) -> str:
    name = (
        getattr(panel, "panel_name", None)
        or getattr(panel, "name", None)
        or getattr(panel, "panel_serial", None)
        or getattr(panel, "serial", None)
    )
    host = getattr(panel, "panel_host", None) or getattr(panel, "host", None)
    model = getattr(panel, "panel_model", None) or getattr(panel, "model", None)
    mac = getattr(panel, "panel_mac", None) or getattr(panel, "mac", None)
    details = ", ".join(
        value
        for value in (
            str(model) if model else None,
            str(mac) if mac else None,
            str(host) if host else None,
        )
        if value
    )
    base = str(name) if name else "Panel"
    label = f"{base} ({details})" if details else base
    if already_configured:
        return f"{label} (already configured)"
    return label


def _snapshot_to_dict(snapshot: Any) -> dict[str, Any]:
    """Serialize a snapshot to a dict."""
    if snapshot is None:
        return {}
    if is_dataclass(snapshot) and not isinstance(snapshot, type):
        return asdict(snapshot)
    if isinstance(snapshot, dict):
        return dict(snapshot)
    return {
        key: value
        for key, value in snapshot.__dict__.items()
        if not key.startswith("_")
    }
