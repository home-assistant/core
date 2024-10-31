"""Adds config flow for Trafikverket Train integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import logging
from typing import Any

from pytrafikverket import TrafikverketTrain
from pytrafikverket.exceptions import (
    InvalidAuthentication,
    MultipleTrainStationsFound,
    NoTrainAnnouncementFound,
    NoTrainStationFound,
    UnknownError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_WEEKDAY, WEEKDAYS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TimeSelector,
)
import homeassistant.util.dt as dt_util

from .const import CONF_FILTER_PRODUCT, CONF_FROM, CONF_TIME, CONF_TO, DOMAIN
from .util import create_unique_id, next_departuredate

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


async def validate_input(
    hass: HomeAssistant,
    api_key: str,
    train_from: str,
    train_to: str,
    train_time: str | None,
    weekdays: list[str],
    product_filter: str | None,
) -> dict[str, str]:
    """Validate input from user input."""
    errors: dict[str, str] = {}

    when = dt_util.now()
    if train_time:
        departure_day = next_departuredate(weekdays)
        if _time := dt_util.parse_time(train_time):
            when = datetime.combine(
                departure_day,
                _time,
                dt_util.get_default_time_zone(),
            )

    try:
        web_session = async_get_clientsession(hass)
        train_api = TrafikverketTrain(web_session, api_key)
        from_station = await train_api.async_get_train_station(train_from)
        to_station = await train_api.async_get_train_station(train_to)
        if train_time:
            await train_api.async_get_train_stop(
                from_station, to_station, when, product_filter
            )
        else:
            await train_api.async_get_next_train_stop(
                from_station, to_station, when, product_filter
            )
    except InvalidAuthentication:
        errors["base"] = "invalid_auth"
    except NoTrainStationFound:
        errors["base"] = "invalid_station"
    except MultipleTrainStationsFound:
        errors["base"] = "more_stations"
    except NoTrainAnnouncementFound:
        errors["base"] = "no_trains"
    except UnknownError as error:
        _LOGGER.error("Unknown error occurred during validation %s", str(error))
        errors["base"] = "cannot_connect"
    except Exception as error:  # noqa: BLE001
        _LOGGER.error("Unknown exception occurred during validation %s", str(error))
        errors["base"] = "cannot_connect"

    return errors


class TVTrainConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafikverket Train integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> TVTrainOptionsFlowHandler:
        """Get the options flow for this handler."""
        return TVTrainOptionsFlowHandler(config_entry)

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
            errors = await validate_input(
                self.hass,
                api_key,
                reauth_entry.data[CONF_FROM],
                reauth_entry.data[CONF_TO],
                reauth_entry.data.get(CONF_TIME),
                reauth_entry.data[CONF_WEEKDAY],
                reauth_entry.options.get(CONF_FILTER_PRODUCT),
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

            errors = await validate_input(
                self.hass,
                api_key,
                train_from,
                train_to,
                train_time,
                train_days,
                filter_product,
            )
            if not errors:
                unique_id = create_unique_id(
                    train_from, train_to, train_time, train_days
                )
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
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

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, user_input or {}
            ),
            errors=errors,
        )


class TVTrainOptionsFlowHandler(OptionsFlowWithConfigEntry):
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
                user_input or self.options,
            ),
            errors=errors,
        )
