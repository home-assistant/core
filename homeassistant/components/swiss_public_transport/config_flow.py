"""Config flow for swiss_public_transport."""

import logging
from typing import Any

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    DurationSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from .const import (
    CONF_DESTINATION,
    CONF_START,
    CONF_TIME_FIXED,
    CONF_TIME_MODE,
    CONF_TIME_OFFSET,
    CONF_TIME_STATION,
    CONF_VIA,
    DEFAULT_TIME_MODE,
    DEFAULT_TIME_STATION,
    DOMAIN,
    IS_ARRIVAL_OPTIONS,
    MAX_VIA,
    PLACEHOLDERS,
    TIME_MODE_OPTIONS,
)
from .helper import offset_opendata, unique_id_from_config

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_START): cv.string,
        vol.Optional(CONF_VIA): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            ),
        ),
        vol.Required(CONF_DESTINATION): cv.string,
        vol.Optional(CONF_TIME_MODE, default=DEFAULT_TIME_MODE): SelectSelector(
            SelectSelectorConfig(
                options=TIME_MODE_OPTIONS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="time_mode",
            ),
        ),
        vol.Optional(CONF_TIME_STATION, default=DEFAULT_TIME_STATION): SelectSelector(
            SelectSelectorConfig(
                options=IS_ARRIVAL_OPTIONS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="time_station",
            ),
        ),
    }
)
ADVANCED_TIME_DATA_SCHEMA = {vol.Optional(CONF_TIME_FIXED): TimeSelector()}
ADVANCED_TIME_OFFSET_DATA_SCHEMA = {vol.Optional(CONF_TIME_OFFSET): DurationSelector()}


_LOGGER = logging.getLogger(__name__)


class SwissPublicTransportConfigFlow(ConfigFlow, domain=DOMAIN):
    """Swiss public transport config flow."""

    VERSION = 3
    MINOR_VERSION = 1

    user_input: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Async user step to set up the connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if CONF_VIA in user_input and len(user_input[CONF_VIA]) > MAX_VIA:
                errors["base"] = "too_many_via_stations"
            else:
                err = await self.fetch_connections(user_input)
                if err:
                    errors["base"] = err
                else:
                    self.user_input = user_input
                    if user_input[CONF_TIME_MODE] == "fixed":
                        return await self.async_step_time_fixed()
                    if user_input[CONF_TIME_MODE] == "offset":
                        return await self.async_step_time_offset()

                    unique_id = unique_id_from_config(user_input)
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=unique_id,
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=USER_DATA_SCHEMA,
                suggested_values=user_input,
            ),
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )

    async def async_step_time_fixed(
        self, time_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Async time step to set up the connection."""
        return await self._async_step_time_mode(
            CONF_TIME_FIXED, vol.Schema(ADVANCED_TIME_DATA_SCHEMA), time_input
        )

    async def async_step_time_offset(
        self, time_offset_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Async time offset step to set up the connection."""
        return await self._async_step_time_mode(
            CONF_TIME_OFFSET,
            vol.Schema(ADVANCED_TIME_OFFSET_DATA_SCHEMA),
            time_offset_input,
        )

    async def _async_step_time_mode(
        self,
        step_id: str,
        time_mode_schema: vol.Schema,
        time_mode_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Async time mode step to set up the connection."""
        errors: dict[str, str] = {}
        if time_mode_input is not None:
            unique_id = unique_id_from_config({**self.user_input, **time_mode_input})
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            err = await self.fetch_connections(
                {**self.user_input, **time_mode_input},
                time_mode_input.get(CONF_TIME_OFFSET),
            )
            if err:
                errors["base"] = err
            else:
                return self.async_create_entry(
                    title=unique_id,
                    data={**self.user_input, **time_mode_input},
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=time_mode_schema,
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )

    async def fetch_connections(
        self, input: dict[str, Any], time_offset: dict[str, int] | None = None
    ) -> str | None:
        """Fetch the connections and advancedly return an error."""
        try:
            session = async_get_clientsession(self.hass)
            opendata = OpendataTransport(
                input[CONF_START],
                input[CONF_DESTINATION],
                session,
                via=input.get(CONF_VIA),
                time=input.get(CONF_TIME_FIXED),
            )
            if time_offset:
                offset_opendata(opendata, time_offset)
            await opendata.async_get_data()
        except OpendataTransportConnectionError:
            return "cannot_connect"
        except OpendataTransportError:
            return "bad_config"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error")
            return "unknown"
        return None
