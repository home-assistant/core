"""Config flow for the Linksys Smart Wi-Fi integration."""

from collections.abc import Awaitable
import logging
from typing import Any, TypeVar, override

from jnap import JNAPError, JNAPUnauthorizedError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .util import build_client

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Optional(CONF_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)


async def _async_map_jnap_errors(
    call: Awaitable[_T],
) -> tuple[_T | None, dict[str, str]]:
    """Await a JNAP call, mapping exceptions to form errors."""
    errors: dict[str, str] = {}
    try:
        result = await call
    except JNAPUnauthorizedError:
        errors["base"] = "invalid_auth"
    except JNAPError:
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    else:
        return result, errors
    return None, errors


class LinksysConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for linksys."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            client = build_client(self.hass, user_input)
            device_info, errors = await _async_map_jnap_errors(client.get_device_info())
            if device_info is not None:
                await self.async_set_unique_id(device_info.serial_number)
                self._abort_if_unique_id_configured()
                _, errors = await _async_map_jnap_errors(client.get_devices())
                if not errors:
                    return self.async_create_entry(
                        title=device_info.description, data=user_input
                    )
        else:
            errors = {}

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a router discovered via YAML, without requiring credentials."""
        client = build_client(self.hass, import_data)
        device_info, errors = await _async_map_jnap_errors(client.get_device_info())
        if device_info is not None:
            await self.async_set_unique_id(device_info.serial_number)
            self._abort_if_unique_id_configured()
            _, errors = await _async_map_jnap_errors(client.get_devices())
            if not errors:
                return self.async_create_entry(
                    title=device_info.description, data=import_data
                )

        if errors["base"] == "cannot_connect":
            translation_key = "deprecated_yaml_import_issue_cannot_connect"
        elif errors["base"] == "invalid_auth":
            translation_key = "deprecated_yaml_import_issue_credentials_required"
        else:
            translation_key = "deprecated_yaml_import_issue_unknown"
        host = import_data[CONF_HOST]
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"{translation_key}_{host}",
            breaks_in_ha_version="2027.1.0",
            is_fixable=False,
            is_persistent=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=translation_key,
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Linksys Smart Wi-Fi",
                "host": host,
            },
        )
        return self.async_abort(reason=errors["base"])
