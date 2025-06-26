"""Adds config flow for Trafikverket Train integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pytrafikverket import (
    InvalidAuthentication,
    NoTrainStationFound,
    StationInfoModel,
    TrafikverketTrain,
    UnknownError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_WEEKDAY, WEEKDAYS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TimeSelector,
)

from .const import CONF_FILTER_PRODUCT, CONF_FROM, CONF_TIME, CONF_TO, DOMAIN

_LOGGER = logging.getLogger(__name__)

OPTION_SCHEMA = {
    vol.Optional(CONF_FILTER_PRODUCT, default=""): TextSelector(),
}

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(),
        vol.Required(CONF_FROM): TextSelector(),
        vol.Required(CONF_TO): TextSelector(),
        vol.Optional(CONF_TIME): TimeSelector(),
        vol.Required(CONF_WEEKDAY, default=WEEKDAYS): SelectSelector(
            SelectSelectorConfig(
                options=WEEKDAYS,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_WEEKDAY,
            )
        ),
    }
).extend(OPTION_SCHEMA)
DATA_SCHEMA_REAUTH = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
    }
)


async def validate_station(
    hass: HomeAssistant,
    api_key: str,
    train_station: str,
    field: str,
) -> tuple[list[StationInfoModel], dict[str, str]]:
    """Validate input from user input."""
    errors: dict[str, str] = {}
    stations = []
    try:
        web_session = async_get_clientsession(hass)
        train_api = TrafikverketTrain(web_session, api_key)
        stations = await train_api.async_search_train_stations(train_station)
    except InvalidAuthentication:
        errors["base"] = "invalid_auth"
    except NoTrainStationFound:
        errors[field] = "invalid_station"
    except UnknownError as error:
        _LOGGER.error("Unknown error occurred during validation %s", str(error))
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unknown exception occurred during validation")
        errors["base"] = "cannot_connect"

    return (stations, errors)


class TVTrainConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafikverket Train integration."""

    VERSION = 2
    MINOR_VERSION = 1

    _from_stations: list[StationInfoModel]
    _to_stations: list[StationInfoModel]
    _time: str | None
    _days: list
    _product: str | None
    _data: dict[str, Any]

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> TVTrainOptionsFlowHandler:
        """Get the options flow for this handler."""
        return TVTrainOptionsFlowHandler()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication with Trafikverket."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with Trafikverket."""
        errors: dict[str, str] = {}

        if user_input:
            api_key = user_input[CONF_API_KEY]

            reauth_entry = self._get_reauth_entry()
            _, errors = await validate_station(
                self.hass,
                api_key,
                reauth_entry.data[CONF_FROM],
                CONF_FROM,
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=DATA_SCHEMA_REAUTH,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        return await self.async_step_initial(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        return await self.async_step_initial(user_input)

    async def async_step_initial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key: str = user_input[CONF_API_KEY]
            train_from: str = user_input[CONF_FROM]
            train_to: str = user_input[CONF_TO]
            train_time: str | None = user_input.get(CONF_TIME)
            train_days: list = user_input[CONF_WEEKDAY]
            filter_product: str | None = user_input[CONF_FILTER_PRODUCT]

            if filter_product == "":
                filter_product = None

            name = f"{train_from} to {train_to}"
            if train_time:
                name = f"{train_from} to {train_to} at {train_time}"

            self._from_stations, from_errors = await validate_station(
                self.hass, api_key, train_from, CONF_FROM
            )
            self._to_stations, to_errors = await validate_station(
                self.hass, api_key, train_to, CONF_TO
            )
            errors = {**from_errors, **to_errors}

            if not errors:
                if len(self._from_stations) == 1 and len(self._to_stations) == 1:
                    self._async_abort_entries_match(
                        {
                            CONF_API_KEY: api_key,
                            CONF_FROM: self._from_stations[0].signature,
                            CONF_TO: self._to_stations[0].signature,
                            CONF_TIME: train_time,
                            CONF_WEEKDAY: train_days,
                            CONF_FILTER_PRODUCT: filter_product,
                        }
                    )

                    if self.source == SOURCE_RECONFIGURE:
                        reconfigure_entry = self._get_reconfigure_entry()
                        return self.async_update_reload_and_abort(
                            reconfigure_entry,
                            title=name,
                            data={
                                CONF_API_KEY: api_key,
                                CONF_NAME: name,
                                CONF_FROM: self._from_stations[0].signature,
                                CONF_TO: self._to_stations[0].signature,
                                CONF_TIME: train_time,
                                CONF_WEEKDAY: train_days,
                            },
                            options={CONF_FILTER_PRODUCT: filter_product},
                        )
                    return self.async_create_entry(
                        title=name,
                        data={
                            CONF_API_KEY: api_key,
                            CONF_NAME: name,
                            CONF_FROM: self._from_stations[0].signature,
                            CONF_TO: self._to_stations[0].signature,
                            CONF_TIME: train_time,
                            CONF_WEEKDAY: train_days,
                        },
                        options={CONF_FILTER_PRODUCT: filter_product},
                    )
                self._data = user_input
                return await self.async_step_select_stations()

        return self.async_show_form(
            step_id="initial",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, user_input or {}
            ),
            errors=errors,
        )

    async def async_step_select_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the select station step."""
        if user_input is not None:
            api_key: str = self._data[CONF_API_KEY]
            train_from: str = (
                user_input.get(CONF_FROM) or self._from_stations[0].signature
            )
            train_to: str = user_input.get(CONF_TO) or self._to_stations[0].signature
            train_time: str | None = self._data.get(CONF_TIME)
            train_days: list = self._data[CONF_WEEKDAY]
            filter_product: str | None = self._data[CONF_FILTER_PRODUCT]

            if filter_product == "":
                filter_product = None

            name = f"{self._data[CONF_FROM]} to {self._data[CONF_TO]}"
            if train_time:
                name = (
                    f"{self._data[CONF_FROM]} to {self._data[CONF_TO]} at {train_time}"
                )
            self._async_abort_entries_match(
                {
                    CONF_API_KEY: api_key,
                    CONF_FROM: train_from,
                    CONF_TO: train_to,
                    CONF_TIME: train_time,
                    CONF_WEEKDAY: train_days,
                    CONF_FILTER_PRODUCT: filter_product,
                }
            )
            if self.source == SOURCE_RECONFIGURE:
                reconfigure_entry = self._get_reconfigure_entry()
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=name,
                    data={
                        CONF_API_KEY: api_key,
                        CONF_NAME: name,
                        CONF_FROM: train_from,
                        CONF_TO: train_to,
                        CONF_TIME: train_time,
                        CONF_WEEKDAY: train_days,
                    },
                    options={CONF_FILTER_PRODUCT: filter_product},
                )
            return self.async_create_entry(
                title=name,
                data={
                    CONF_API_KEY: api_key,
                    CONF_NAME: name,
                    CONF_FROM: train_from,
                    CONF_TO: train_to,
                    CONF_TIME: train_time,
                    CONF_WEEKDAY: train_days,
                },
                options={CONF_FILTER_PRODUCT: filter_product},
            )
        from_options = [
            SelectOptionDict(value=station.signature, label=station.station_name)
            for station in self._from_stations
        ]
        to_options = [
            SelectOptionDict(value=station.signature, label=station.station_name)
            for station in self._to_stations
        ]
        schema = {}
        if len(from_options) > 1:
            schema[vol.Required(CONF_FROM)] = SelectSelector(
                SelectSelectorConfig(
                    options=from_options, mode=SelectSelectorMode.DROPDOWN, sort=True
                )
            )
        if len(to_options) > 1:
            schema[vol.Required(CONF_TO)] = SelectSelector(
                SelectSelectorConfig(
                    options=to_options, mode=SelectSelectorMode.DROPDOWN, sort=True
                )
            )

        return self.async_show_form(
            step_id="select_stations",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema), user_input or {}
            ),
        )


class TVTrainOptionsFlowHandler(OptionsFlow):
    """Handle Trafikverket Train options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Trafikverket Train options."""
        errors: dict[str, Any] = {}

        if user_input:
            if not (_filter := user_input.get(CONF_FILTER_PRODUCT)) or _filter == "":
                user_input[CONF_FILTER_PRODUCT] = None
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(OPTION_SCHEMA),
                user_input or self.config_entry.options,
            ),
            errors=errors,
        )
