"""Config flow for the Elke27 integration."""

from collections.abc import Mapping
import contextlib
from dataclasses import asdict, is_dataclass
import re
from typing import Any

from elke27_lib import ClientConfig, LinkKeys
from elke27_lib.client import Elke27Client
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
from homeassistant.const import CONF_CLIENT_ID, CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import selector

from .const import CONF_LINK_KEYS_JSON, DEFAULT_PORT, DOMAIN, READY_TIMEOUT
from .identity import build_client_identity, derive_client_id

CONF_ACCESS_CODE = "access_code"
CONF_PASSPHRASE = "passphrase"
CONF_PANEL_INFO = "panel_info"
CONF_TABLE_INFO = "table_info"

_UNIQUE_ID_RE = re.compile(r"[^a-z0-9]")

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_ACCESS_CODE): selector({"text": {"type": "password"}}),
        vol.Required(CONF_PASSPHRASE): selector({"text": {"type": "password"}}),
    }
)


class Elke27ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elke27."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._selected_host: str | None = None
        self._selected_port: int | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = DEFAULT_PORT
            self._selected_host = host
            self._selected_port = port
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

    async def _async_link_and_create_entry(
        self,
        access_code: str,
        passphrase: str,
        errors: dict[str, str],
        step_id: str,
        data_schema: vol.Schema,
    ) -> ConfigFlowResult:
        """Link, connect, fetch snapshots, and create the entry."""
        host = self._selected_host
        port = self._selected_port
        if host is None or port is None:
            errors["base"] = "unknown"
            return self.async_show_form(
                step_id=step_id,
                data_schema=data_schema,
                errors=errors,
            )

        client_id = derive_client_id(self.flow_id)
        client_identity = build_client_identity(client_id)
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
            panel_info = _snapshot_to_dict(snapshot.panel)
            table_info = _snapshot_to_dict(snapshot.table_info)
        except InvalidCredentials:
            errors["base"] = "invalid_auth"
        except Elke27AuthError:
            errors["base"] = "cannot_connect"
        except (
            Elke27ConnectionError,
            Elke27TimeoutError,
            Elke27DisconnectedError,
            OSError,
        ):
            errors["base"] = "cannot_connect"
        except Elke27LinkRequiredError:
            errors["base"] = "link_required"
        except Elke27Error:
            errors["base"] = "unknown"
        finally:
            with contextlib.suppress(Exception):
                await client.async_disconnect()

        if errors or link_keys is None:
            return self.async_show_form(
                step_id=step_id,
                data_schema=data_schema,
                errors=errors,
            )

        link_keys_json = link_keys.to_json()
        panel_unique_id = _panel_unique_id(panel_info)
        if panel_unique_id is not None:
            await self.async_set_unique_id(panel_unique_id)
            self._abort_if_unique_id_configured()
        data: dict[str, Any] = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_LINK_KEYS_JSON: link_keys_json,
            CONF_CLIENT_ID: client_id,
        }

        options: dict[str, Any] = {
            CONF_PANEL_INFO: panel_info,
            CONF_TABLE_INFO: table_info,
        }

        title = _panel_name(panel_info) or host
        result = self.async_create_entry(title=title, data=data, options=options)
        if "title" not in result:
            result["title"] = title
        return result


def _create_client() -> Elke27Client:
    """Create a configured client instance."""
    return Elke27Client(ClientConfig())


def _panel_name(panel_info: dict[str, Any]) -> str | None:
    return (
        panel_info.get("panel_name")
        or panel_info.get("name")
        or panel_info.get("serial")
        or panel_info.get("panel_serial")
    )


def _panel_unique_id(panel_info: dict[str, Any]) -> str | None:
    """Return the stable panel identifier from panel info."""
    unique_id = (
        panel_info.get("serial")
        or panel_info.get("panel_serial")
        or panel_info.get("mac")
        or panel_info.get("panel_mac")
    )
    if unique_id is None:
        return None
    normalized = _UNIQUE_ID_RE.sub("", str(unique_id).lower())
    return normalized or None


def _snapshot_to_dict(snapshot: Any) -> dict[str, Any]:
    """Serialize a snapshot to a dict."""
    if snapshot is None:
        return {}
    if is_dataclass(snapshot) and not isinstance(snapshot, type):
        return asdict(snapshot)
    if isinstance(snapshot, Mapping):
        return dict(snapshot)
    return {}
