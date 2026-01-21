"""Config flow for the Elke27 integration."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from elke27_lib import ClientConfig, Elke27Client, LinkKeys
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

CONF_ACCESS_CODE = "access_code"
CONF_PASSPHRASE = "passphrase"
CONF_PANEL_INFO = "panel_info"
CONF_TABLE_INFO = "table_info"

STEP_USER_DATA_SCHEMA = vol.Schema(
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
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
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
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


def _create_client() -> Elke27Client:
    """Create a configured client instance."""
    return Elke27Client(ClientConfig())


def _panel_to_dict(panel: Any | None) -> dict[str, Any]:
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


def _panel_mac(panel_info: dict[str, Any]) -> str | None:
    return panel_info.get("mac") or panel_info.get("panel_mac")


def _panel_name(panel_info: dict[str, Any]) -> str | None:
    return (
        panel_info.get("panel_name")
        or panel_info.get("name")
        or panel_info.get("serial")
        or panel_info.get("panel_serial")
    )


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
