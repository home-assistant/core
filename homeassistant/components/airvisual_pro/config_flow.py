"""Define a config flow manager for AirVisual Pro."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pyairvisual.node import (
    InvalidAuthenticationError,
    NodeConnectionError,
    NodeProError,
    NodeSamba,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD

from .const import DOMAIN, LOGGER

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


@dataclass
class ValidationResult:
    """Define a validation result."""

    serial_number: str | None = None
    errors: dict[str, Any] = field(default_factory=dict)


async def async_validate_credentials(
    ip_address: str, password: str
) -> ValidationResult:
    """Validate an IP address/password combo."""
    node = NodeSamba(ip_address, password)
    errors = {}

    try:
        await node.async_connect()
        measurements = await node.async_get_latest_measurements()
    except InvalidAuthenticationError as err:
        LOGGER.error("Invalid password for Pro at IP address %s: %s", ip_address, err)
        errors["base"] = "invalid_auth"
    except NodeConnectionError as err:
        LOGGER.error("Cannot connect to Pro at IP address %s: %s", ip_address, err)
        errors["base"] = "cannot_connect"
    except NodeProError as err:
        LOGGER.error("Unknown Pro error while connecting to %s: %s", ip_address, err)
        errors["base"] = "unknown"
    except Exception as err:  # pylint: disable=broad-except
        LOGGER.exception("Unknown error while connecting to %s: %s", ip_address, err)
        errors["base"] = "unknown"
    else:
        return ValidationResult(serial_number=measurements["serial_number"])
    finally:
        await node.async_disconnect()

    return ValidationResult(errors=errors)


class AirVisualProFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an AirVisual Pro config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the re-auth step."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=STEP_REAUTH_SCHEMA
            )

        assert self._reauth_entry

        validation_result = await async_validate_credentials(
            self._reauth_entry.data[CONF_IP_ADDRESS], user_input[CONF_PASSWORD]
        )

        if validation_result.errors:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_REAUTH_SCHEMA,
                errors=validation_result.errors,
            )

        self.hass.config_entries.async_update_entry(
            self._reauth_entry, data=self._reauth_entry.data | user_input
        )
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
        )
        return self.async_abort(reason="reauth_successful")

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if not user_input:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

        ip_address = user_input[CONF_IP_ADDRESS]

        validation_result = await async_validate_credentials(
            ip_address, user_input[CONF_PASSWORD]
        )

        if validation_result.errors:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_SCHEMA,
                errors=validation_result.errors,
            )

        await self.async_set_unique_id(validation_result.serial_number)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=ip_address, data=user_input)
