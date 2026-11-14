"""Configuration and authentication flows for IAMMETER."""

from collections.abc import Mapping
import logging
from typing import Any, override

from iammeter.async_client import IammeterAuthError, IammeterConnectionError
from iammeter.connection import normalize_connection
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv, selector

from .const import DEFAULT_PORT, DOMAIN
from .coordinator import async_get_meter, meter_identity

_LOGGER = logging.getLogger(__name__)
CONNECTION_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Optional(CONF_USERNAME, default=""): cv.string,
        probatio.Optional(CONF_PASSWORD, default=""): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


class IammeterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure one meter using a stable device identity."""

    VERSION = 1
    MINOR_VERSION = 2

    async def _async_validate_input(
        self, data: dict[str, Any]
    ) -> tuple[str | None, dict[str, Any]]:
        try:
            data[CONF_HOST], data[CONF_PORT], _ = normalize_connection(
                data[CONF_HOST], data.get(CONF_PORT, DEFAULT_PORT)
            )
        except ValueError:
            return "invalid_host", {}
        if data.get(CONF_PASSWORD) and not data.get(CONF_USERNAME):
            return "invalid_auth", {}
        try:
            meter = await async_get_meter(self.hass, data)
        except IammeterAuthError:
            return "invalid_auth", {}
        except IammeterConnectionError, TimeoutError:
            return "cannot_connect", {}
        except ValueError:
            return "invalid_data", {}
        except Exception:
            _LOGGER.exception("Unexpected error connecting to IAMMETER")
            return "unknown", {}
        await self.async_set_unique_id(meter_identity(meter))
        return None, meter

    def _connection_data(self, data: dict[str, Any]) -> dict[str, Any]:
        result = {CONF_HOST: data[CONF_HOST], CONF_PORT: data[CONF_PORT]}
        for key in (CONF_USERNAME, CONF_PASSWORD):
            if data.get(key):
                result[key] = data[key]
        return result

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            error, meter = await self._async_validate_input(user_input)
            if error:
                errors["base"] = error
            else:
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"IAMMETER {meter['Model']} {self.unique_id}",
                    data=self._connection_data(user_input),
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                CONNECTION_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import the existing YAML configuration without renaming entities."""
        data = {
            CONF_HOST: import_data[CONF_HOST],
            CONF_PORT: import_data.get(CONF_PORT, DEFAULT_PORT),
        }
        error, meter = await self._async_validate_input(data)
        if error:
            return self.async_abort(reason=error)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=import_data.get(
                CONF_NAME, f"IAMMETER {meter['Model']} {self.unique_id}"
            ),
            data=self._connection_data(data),
        )

    async def _async_connection_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        entry = (
            self._get_reauth_entry()
            if step_id == "reauth_confirm"
            else self._get_reconfigure_entry()
        )
        errors = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            error, _ = await self._async_validate_input(data)
            if error:
                errors["base"] = error
            else:
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry, data=self._connection_data(data)
                )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                CONNECTION_SCHEMA, user_input or dict(entry.data)
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update the address of the same physical meter."""
        return await self._async_connection_step("reconfigure", user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Request corrected credentials after authentication failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate the identity before accepting replacement credentials."""
        return await self._async_connection_step("reauth_confirm", user_input)
