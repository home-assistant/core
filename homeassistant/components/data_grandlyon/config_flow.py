"""Config flow for the Data Grand Lyon integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError
from data_grand_lyon_ha import DataGrandLyonClient, TclPassageType
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LINE, CONF_STOP_ID, DOMAIN, SUBENTRY_TYPE_STOP

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_STOP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LINE): str,
        vol.Required(CONF_STOP_ID): vol.Coerce(int),
        vol.Optional(CONF_NAME): str,
    }
)


class DataGrandLyonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Data Grand Lyon."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry types supported by this integration."""
        return {
            SUBENTRY_TYPE_STOP: StopSubentryFlowHandler,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match()

            data: dict[str, Any] = {}
            if username := user_input.get(CONF_USERNAME):
                data[CONF_USERNAME] = username
            if password := user_input.get(CONF_PASSWORD):
                data[CONF_PASSWORD] = password

            if error := await self._test_connection(data):
                errors["base"] = error
            else:
                return self.async_create_entry(title="Data Grand Lyon", data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def _test_connection(self, data: dict[str, Any]) -> str | None:
        """Test connectivity by making a dummy API call.

        Returns None on success, or an error key for the errors dict.
        """
        session = async_get_clientsession(self.hass)
        client = DataGrandLyonClient(
            session=session,
            username=data.get(CONF_USERNAME),
            password=data.get(CONF_PASSWORD),
        )
        try:
            # the upstream library filters in memory so these placeholder values
            # won't trigger an exception ; the returned list will be empty
            await client.get_tcl_passages(
                ligne="__test__", stop_id=0, passage_type=TclPassageType.ESTIMATED
            )
        except ClientResponseError as err:
            if err.status in (401, 403):
                return "invalid_auth"
            return "cannot_connect"
        except ClientError, TimeoutError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error testing Data Grand Lyon connection")
            return "unknown"
        return None


class StopSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for adding a Data Grand Lyon stop."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the user step to add a new stop."""
        entry = self._get_entry()
        if not entry.data.get(CONF_USERNAME):
            return self.async_abort(reason="auth_required")

        if user_input is not None:
            line = user_input[CONF_LINE]
            stop_id = user_input[CONF_STOP_ID]
            unique_id = f"{line}_{stop_id}"

            for subentry in entry.subentries.values():
                if subentry.unique_id == unique_id:
                    return self.async_abort(reason="already_configured")

            name = user_input.get(CONF_NAME) or f"{line} - Stop {stop_id}"
            return self.async_create_entry(
                title=name,
                data={CONF_LINE: line, CONF_STOP_ID: stop_id},
                unique_id=unique_id,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_STOP_DATA_SCHEMA,
        )
