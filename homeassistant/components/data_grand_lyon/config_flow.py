"""Config flow for the Data Grand Lyon integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aiohttp import ClientError, ClientResponseError
from data_grand_lyon_ha import (
    DataGrandLyonClient,
    TclStop,
    VelovStation,
    find_tcl_stop_by_id,
)
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
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

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


class DataGrandLyonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Data Grand Lyon."""

    VERSION = 1

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry types supported by this integration."""
        return {
            SUBENTRY_TYPE_STOP: StopSubentryFlowHandler,
            SUBENTRY_TYPE_VELOV_STATION: VelovStationSubentryFlowHandler,
        }

    @override
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

    def __init__(self) -> None:
        """Initialize the flow."""
        self._stops: list[TclStop] = []
        self._selected_stop: TclStop | None = None
        self._selected_stop_id: int | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Pick a stop from the list fetched from the API, or enter one manually."""
        if not self._stops:
            if error := await self._async_load_stops():
                return self.async_abort(reason=error)

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                stop_id = int(user_input[CONF_STOP_ID])
            except ValueError:
                errors[CONF_STOP_ID] = "invalid_stop_id"
            else:
                self._selected_stop_id = stop_id
                self._selected_stop = find_tcl_stop_by_id(self._stops, stop_id)
                return await self.async_step_pick_line()

        options = [
            SelectOptionDict(value=str(stop.id), label=_stop_label(stop))
            for stop in sorted(
                self._stops, key=lambda s: (s.nom, s.commune or "", s.id or 0)
            )
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_STOP_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                        sort=False,
                        custom_value=True,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_pick_line(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Pick a line from the selected stop's desserte, or enter one manually."""
        assert self._selected_stop_id is not None
        if user_input is not None:
            return self._create_stop(
                line=user_input[CONF_LINE], stop_id=self._selected_stop_id
            )

        options = self._selected_stop.desserte if self._selected_stop else []
        schema = vol.Schema(
            {
                vol.Required(CONF_LINE): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                )
            }
        )
        return self.async_show_form(step_id="pick_line", data_schema=schema)

    async def _async_load_stops(self) -> str | None:
        """Fetch TCL stops from the API, returning an error key on failure."""
        entry = self._get_entry()
        session = async_get_clientsession(self.hass)
        client = DataGrandLyonClient(
            session=session,
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
        )
        try:
            self._stops = await client.get_tcl_stops()
        except ClientResponseError as err:
            if err.status in (401, 403):
                return "invalid_auth"
            return "cannot_connect"
        except ClientError, TimeoutError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error fetching Data Grand Lyon TCL stops")
            return "unknown"
        return None

    def _create_stop(self, line: str, stop_id: int) -> SubentryFlowResult:
        """Create the stop subentry, aborting on duplicate."""
        entry = self._get_entry()
        unique_id = f"{line}_{stop_id}"
        for subentry in entry.subentries.values():
            if subentry.unique_id == unique_id:
                return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title=f"{line} - Stop {stop_id}",
            data={CONF_LINE: line, CONF_STOP_ID: stop_id},
            unique_id=unique_id,
        )


def _stop_label(stop: TclStop) -> str:
    label = stop.nom
    # variable extracted to please codespell.
    address = stop.adresse  # codespell:ignore adresse
    if address or stop.commune:
        label += " (" + ", ".join(filter(None, [address, stop.commune])) + ")"
    label += f" - {stop.id}"

    return label


class VelovStationSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for adding a Vélo'v station."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self._stations: list[VelovStation] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Pick a station from the list fetched from the API, or enter one manually."""
        if not self._stations:
            if error := await self._async_load_stations():
                return self.async_abort(reason=error)

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                station_id = int(user_input[CONF_STATION_ID])
            except ValueError:
                errors[CONF_STATION_ID] = "invalid_station_id"
            else:
                entry = self._get_entry()
                unique_id = f"velov_{station_id}"

                for subentry in entry.subentries.values():
                    if subentry.unique_id == unique_id:
                        return self.async_abort(reason="already_configured")

                return self.async_create_entry(
                    title=f"Vélo'v {station_id}",
                    data={CONF_STATION_ID: station_id},
                    unique_id=unique_id,
                )

        options = [
            SelectOptionDict(
                value=str(station.number), label=_velov_station_label(station)
            )
            for station in sorted(
                self._stations,
                key=lambda s: (s.name, s.commune or "", s.number or 0),
            )
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_STATION_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                        sort=False,
                        custom_value=True,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def _async_load_stations(self) -> str | None:
        """Fetch Vélo'v stations from the API, returning an error key on failure."""
        entry = self._get_entry()
        session = async_get_clientsession(self.hass)
        client = DataGrandLyonClient(
            session=session,
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
        )
        try:
            self._stations = await client.get_velov_stations()
        except ClientResponseError as err:
            if err.status in (401, 403):
                return "invalid_auth"
            return "cannot_connect"
        except ClientError, TimeoutError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception(
                "Unexpected error fetching Data Grand Lyon Vélo'v stations"
            )
            return "unknown"
        return None


def _velov_station_label(station: VelovStation) -> str:
    label = station.name
    if station.address or station.commune:
        label += (
            " (" + ", ".join(filter(None, [station.address, station.commune])) + ")"
        )
    label += f" - {station.number}"

    return label
