"""Config flow for the NX584 integration."""

import logging
from typing import Any, override

import probatio
import requests

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers.typing import UNDEFINED

from . import create_client
from .const import (
    CONF_EXCLUDE_ZONES,
    CONF_ZONE_TYPES,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST, default=DEFAULT_HOST): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
    }
)


class NX584ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NX584."""

    VERSION = 1

    def _async_entry_for_server(self, host: str, port: int) -> ConfigEntry | None:
        """Return the entry of the server, if it is set up."""
        return next(
            (
                entry
                for entry in self._async_current_entries(include_ignore=False)
                if entry.data[CONF_HOST] == host and entry.data[CONF_PORT] == port
            ),
            None,
        )

    async def _async_validate(self, host: str, port: int) -> None:
        """Connect to the server; raise if it cannot be reached."""
        client = create_client(host, port)
        await self.hass.async_add_executor_job(client.list_zones)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host: str = user_input[CONF_HOST]
            port: int = user_input[CONF_PORT]
            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})

            try:
                await self._async_validate(host, port)
            except requests.exceptions.ConnectionError, requests.exceptions.Timeout:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Another flow may have set up the server during the validation.
                self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})
                return self.async_create_entry(
                    title=f"{host}:{port}", data={CONF_HOST: host, CONF_PORT: port}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import the YAML configuration of one platform."""
        host: str = import_data[CONF_HOST]
        port: int = import_data[CONF_PORT]
        # Only the alarm platform has a name; it names the entry and the alarm.
        name: str | None = import_data.get(CONF_NAME)
        options: dict[str, Any] = {}
        if CONF_EXCLUDE_ZONES in import_data:
            options[CONF_EXCLUDE_ZONES] = list(import_data[CONF_EXCLUDE_ZONES])
        if CONF_ZONE_TYPES in import_data:
            # Entry options are stored as JSON, so zone numbers become strings.
            options[CONF_ZONE_TYPES] = {
                str(zone): str(zone_type)
                for zone, zone_type in import_data[CONF_ZONE_TYPES].items()
            }

        if not self._async_entry_for_server(host, port):
            try:
                await self._async_validate(host, port)
            except requests.exceptions.ConnectionError, requests.exceptions.Timeout:
                return self.async_abort(reason="cannot_connect")
            except Exception:
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")

        # Checked after the validation, as a user flow may set up the server meanwhile.
        if entry := self._async_entry_for_server(host, port):
            # Each platform owns its keys; the other platform's keys are kept.
            return self.async_update_reload_and_abort(
                entry,
                title=name or UNDEFINED,
                options={**entry.options, **options},
                reason="already_configured",
                reload_even_if_entry_is_unchanged=False,
            )

        return self.async_create_entry(
            title=name or f"{host}:{port}",
            data={CONF_HOST: host, CONF_PORT: port},
            options=options,
        )
