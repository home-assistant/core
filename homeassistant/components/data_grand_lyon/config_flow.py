"""Config flow for the Data Grand Lyon integration."""

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError
from data_grand_lyon_ha import DataGrandLyonClient
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_LINE,
    CONF_STATION_ID,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
    SUBENTRY_TYPE_VELOV_STATION,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_RECONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_STOP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LINE): str,
        vol.Required(CONF_STOP_ID): vol.Coerce(int),
    }
)

STEP_VELOV_STATION_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STATION_ID): vol.Coerce(int),
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
            SUBENTRY_TYPE_VELOV_STATION: VelovStationSubentryFlowHandler,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})

            if error := await self._test_connection(user_input):
                errors["base"] = error
            else:
                return self.async_create_entry(title="Data Grand Lyon", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with new credentials."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            if error := await self._test_connection(user_input):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                {CONF_USERNAME: reauth_entry.data[CONF_USERNAME]},
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of credentials."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            creds = {
                CONF_USERNAME: reconfigure_entry.data.get(CONF_USERNAME),
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            if error := await self._test_connection(creds):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_SCHEMA,
                user_input or reconfigure_entry.data,
            ),
            errors=errors,
        )

    async def _test_connection(self, user_input: dict[str, Any]) -> str | None:
        """Test connectivity by making a dummy API call.

        Returns None on success, or an error key for the errors dict.
        """
        session = async_get_clientsession(self.hass)
        client = DataGrandLyonClient(
            session=session,
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
        )
        try:
            await client.get_tcl_passages()
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

        if user_input is not None:
            line = user_input[CONF_LINE]
            stop_id = user_input[CONF_STOP_ID]
            unique_id = f"{line}_{stop_id}"

            for subentry in entry.subentries.values():
                if subentry.unique_id == unique_id:
                    return self.async_abort(reason="already_configured")

            name = f"{line} - Stop {stop_id}"
            return self.async_create_entry(
                title=name,
                data={CONF_LINE: line, CONF_STOP_ID: stop_id},
                unique_id=unique_id,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_STOP_DATA_SCHEMA,
        )


class VelovStationSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for adding a Vélo'v station."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the user step to add a new Vélo'v station."""
        entry = self._get_entry()

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]
            unique_id = f"velov_{station_id}"

            for subentry in entry.subentries.values():
                if subentry.unique_id == unique_id:
                    return self.async_abort(reason="already_configured")

            return self.async_create_entry(
                title=f"Vélo'v {station_id}",
                data={CONF_STATION_ID: station_id},
                unique_id=unique_id,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_VELOV_STATION_DATA_SCHEMA,
        )
