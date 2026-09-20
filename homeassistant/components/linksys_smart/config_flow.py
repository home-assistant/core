"""Config flow for the Linksys Smart Wi-Fi integration."""

import logging
from typing import Any, override

from jnap import JNAPError, JNAPUnauthorizedError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .util import build_client

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Optional(CONF_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)


async def _async_validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """Validate user input allows us to connect and map exceptions to form errors."""
    client = build_client(hass, data)
    errors: dict[str, str] = {}
    info: dict[str, Any] | None = None
    try:
        device_info = await client.get_device_info()
        await client.get_devices()
    except JNAPUnauthorizedError:
        errors["base"] = "invalid_auth"
    except JNAPError:
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    else:
        info = {
            "title": device_info.description,
            "serial_number": device_info.serial_number,
        }
    return info, errors


class LinksysConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for linksys."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            info, errors = await _async_validate_input(self.hass, user_input)
            if info is not None:
                await self.async_set_unique_id(info["serial_number"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)
        else:
            errors = {}

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a router discovered via YAML, without requiring credentials."""
        info, errors = await _async_validate_input(self.hass, import_data)
        if info is None:
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

        await self.async_set_unique_id(info["serial_number"])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=info["title"], data=import_data)
