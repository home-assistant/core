"""Config flow for the Data Grand Lyon integration."""

from __future__ import annotations

from collections.abc import Mapping
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

from .const import (
    CONF_LINE,
    CONF_STATION_ID,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
    SUBENTRY_TYPE_VELOV,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Inclusive(CONF_USERNAME, "credentials"): str,
        vol.Inclusive(CONF_PASSWORD, "credentials"): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
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

STEP_VELOV_DATA_SCHEMA = vol.Schema(
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
            SUBENTRY_TYPE_VELOV: VelovSubentryFlowHandler,
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the main config entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data: dict[str, Any] = {}
            if username := user_input.get(CONF_USERNAME):
                data[CONF_USERNAME] = username
            if password := user_input.get(CONF_PASSWORD):
                data[CONF_PASSWORD] = password

            if error := await self._test_connection(data):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data=data,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                self._get_reconfigure_entry().data,
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with new credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            if error := await self._test_connection(data):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data=data,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
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
            if data.get(CONF_USERNAME):
                await client.get_tcl_passages(
                    ligne="__test__", stop_id=0, passage_type=TclPassageType.ESTIMATED
                )
            else:
                await client.get_velov_station(0)
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
    """Handle a subentry flow for adding/editing a Data Grand Lyon stop."""

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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of an existing stop."""
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            entry = self._get_entry()
            line = user_input[CONF_LINE]
            stop_id = user_input[CONF_STOP_ID]
            unique_id = f"{line}_{stop_id}"

            for existing_subentry in entry.subentries.values():
                if (
                    existing_subentry.subentry_id != subentry.subentry_id
                    and existing_subentry.unique_id == unique_id
                ):
                    return self.async_abort(reason="already_configured")

            name = user_input.get(CONF_NAME) or f"{line} - Stop {stop_id}"
            self._async_update(
                entry,
                subentry,
                data={CONF_LINE: line, CONF_STOP_ID: stop_id},
                title=name,
                unique_id=unique_id,
            )
            return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_STOP_DATA_SCHEMA,
                {
                    CONF_LINE: subentry.data[CONF_LINE],
                    CONF_STOP_ID: subentry.data[CONF_STOP_ID],
                    CONF_NAME: subentry.title,
                },
            ),
        )


class VelovSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for adding/editing a Vélo'v station."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the user step to add a new Vélo'v station."""
        errors: dict[str, str] = {}

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]
            unique_id = str(station_id)

            entry = self._get_entry()
            for subentry in entry.subentries.values():
                if subentry.unique_id == unique_id:
                    return self.async_abort(reason="already_configured")

            try:
                title = await self._fetch_station_title(station_id)
            except ClientError, TimeoutError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error fetching Vélo'v station")
                errors["base"] = "unknown"
            else:
                if title is None:
                    errors[CONF_STATION_ID] = "station_not_found"
                else:
                    return self.async_create_entry(
                        title=title,
                        data={CONF_STATION_ID: station_id},
                        unique_id=unique_id,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_VELOV_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of an existing Vélo'v station."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]
            unique_id = str(station_id)

            entry = self._get_entry()
            for existing_subentry in entry.subentries.values():
                if (
                    existing_subentry.subentry_id != subentry.subentry_id
                    and existing_subentry.unique_id == unique_id
                ):
                    return self.async_abort(reason="already_configured")

            try:
                title = await self._fetch_station_title(station_id)
            except ClientError, TimeoutError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error fetching Vélo'v station")
                errors["base"] = "unknown"
            else:
                if title is None:
                    errors[CONF_STATION_ID] = "station_not_found"
                else:
                    self._async_update(
                        entry,
                        subentry,
                        data={CONF_STATION_ID: station_id},
                        title=title,
                        unique_id=unique_id,
                    )
                    return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_VELOV_DATA_SCHEMA,
                {CONF_STATION_ID: subentry.data[CONF_STATION_ID]},
            ),
            errors=errors,
        )

    async def _fetch_station_title(self, station_id: int) -> str | None:
        """Fetch the station name from the API, returning None if not found."""
        session = async_get_clientsession(self.hass)
        client = DataGrandLyonClient(session=session)
        station = await client.get_velov_station(station_id)
        if station is None:
            return None
        return station.name
