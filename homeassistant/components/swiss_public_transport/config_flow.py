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
    CONF_IS_ARRIVAL,
    CONF_START,
    CONF_TIME,
    CONF_TIME_MODE,
    CONF_TIME_OFFSET,
    CONF_VIA,
    DEFAULT_TIME_MODE,
    DOMAIN,
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
        vol.Optional(CONF_IS_ARRIVAL): bool,
        vol.Optional(CONF_TIME_MODE): SelectSelector(
            SelectSelectorConfig(
                options=TIME_MODE_OPTIONS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="time_mode",
            ),
        ),
    }
)
ADVANCED_TIME_DATA_SCHEMA = {vol.Optional(CONF_TIME): TimeSelector()}
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
                session = async_get_clientsession(self.hass)
                opendata = OpendataTransport(
                    user_input[CONF_START],
                    user_input[CONF_DESTINATION],
                    session,
                    via=user_input.get(CONF_VIA),
                    time=user_input.get(CONF_TIME),
                )
                err = await self.fetch_connections(opendata)
                if err:
                    errors["base"] = err
                else:
                    if user_input[CONF_TIME_MODE] == "now":
                        unique_id = unique_id_from_config(user_input)
                        await self.async_set_unique_id(unique_id)
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(
                            title=unique_id,
                            data=user_input,
                        )
                    self.user_input = user_input
                    return self.async_show_form(
                        step_id="advanced",
                        data_schema=self.build_advanced_schema(user_input),
                        errors=errors,
                        description_placeholders=PLACEHOLDERS,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=USER_DATA_SCHEMA,
                suggested_values=user_input or {CONF_TIME_MODE: DEFAULT_TIME_MODE},
            ),
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )

    async def async_step_advanced(
        self, advanced_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Async advanced step to set up the connection."""
        errors: dict[str, str] = {}
        if advanced_input is not None:
            unique_id = unique_id_from_config({**self.user_input, **advanced_input})
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            time_offset: dict[str, int] | None = advanced_input.get(CONF_TIME_OFFSET)
            opendata = OpendataTransport(
                self.user_input[CONF_START],
                self.user_input[CONF_DESTINATION],
                session,
                via=self.user_input.get(CONF_VIA),
                time=advanced_input.get(CONF_TIME),
            )
            if time_offset:
                offset_opendata(opendata, time_offset)
            err = await self.fetch_connections(opendata)
            if err:
                errors["base"] = err
            else:
                return self.async_create_entry(
                    title=unique_id,
                    data={**self.user_input, **advanced_input},
                )

        return self.async_show_form(
            step_id="advanced",
            data_schema=self.build_advanced_schema(self.user_input),
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )

    async def fetch_connections(self, opendata: OpendataTransport) -> str | None:
        """Fetch the connections and advancedly return an error."""
        try:
            await opendata.async_get_data()
        except OpendataTransportConnectionError:
            return "cannot_connect"
        except OpendataTransportError:
            return "bad_config"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error")
            return "unknown"
        return None

    def build_advanced_schema(self, user_input: dict[str, Any]) -> vol.Schema:
        """Build the advanced schema."""
        if user_input[CONF_TIME_MODE] == "fixed":
            return vol.Schema(ADVANCED_TIME_DATA_SCHEMA)
        return vol.Schema(ADVANCED_TIME_OFFSET_DATA_SCHEMA)
