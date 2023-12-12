"""Config flow for swiss_public_transport."""
import logging
from typing import Any

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    DateSelector,
    DurationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from .const import (
    CONF_ACCESSIBILITY,
    CONF_BIKE,
    CONF_COUCHETTE,
    CONF_DATE,
    CONF_DESTINATION,
    CONF_DIRECT,
    CONF_IS_ARRIVAL,
    CONF_LIMIT,
    CONF_OFFSET,
    CONF_PAGE,
    CONF_SLEEPER,
    CONF_START,
    CONF_TIME,
    CONF_TRANSPORTATIONS,
    CONF_VIA,
    DEFAULT_IS_ARRIVAL,
    DEFAULT_LIMIT,
    DEFAULT_PAGE,
    DOMAIN,
    MAX_LIMIT,
    MAX_PAGE,
    MAX_VIA,
    MIN_LIMIT,
    MIN_PAGE,
    SELECTOR_ACCESSIBILITY_TYPES,
    SELECTOR_TRANSPORTATION_TYPES,
)
from .helper import (
    dict_duration_to_str_duration,
    entry_title_from_config,
    offset_opendata,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_START): str,
        vol.Required(CONF_DESTINATION): str,
        vol.Optional(CONF_VIA): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            ),
        ),
        vol.Optional(CONF_DATE): DateSelector(),
        vol.Optional(CONF_TIME): TimeSelector(),
        vol.Optional(CONF_OFFSET): DurationSelector(),
        vol.Optional(CONF_IS_ARRIVAL, default=DEFAULT_IS_ARRIVAL): bool,
        vol.Optional(CONF_LIMIT, default=DEFAULT_LIMIT): NumberSelector(
            NumberSelectorConfig(
                min=MIN_LIMIT, max=MAX_LIMIT, mode=NumberSelectorMode.BOX
            )
        ),
        vol.Optional(CONF_PAGE, default=DEFAULT_PAGE): NumberSelector(
            NumberSelectorConfig(
                min=MIN_PAGE, max=MAX_PAGE, mode=NumberSelectorMode.BOX
            )
        ),
        vol.Optional(
            CONF_TRANSPORTATIONS,
        ): SelectSelector(
            SelectSelectorConfig(
                options=SELECTOR_TRANSPORTATION_TYPES,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="transportation",
            ),
        ),
        vol.Optional(
            CONF_ACCESSIBILITY,
        ): SelectSelector(
            SelectSelectorConfig(
                options=SELECTOR_ACCESSIBILITY_TYPES,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="accessibility",
            ),
        ),
        vol.Optional(CONF_DIRECT): bool,
        vol.Optional(CONF_SLEEPER): bool,
        vol.Optional(CONF_COUCHETTE): bool,
        vol.Optional(CONF_BIKE): bool,
    }
)

_LOGGER = logging.getLogger(__name__)


class SwissPublicTransportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Swiss public transport config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Async user step to set up the connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)

            if CONF_VIA in user_input and len(user_input[CONF_VIA]) > MAX_VIA:
                errors["base"] = "too_many_via_stations"
            elif (
                CONF_LIMIT in user_input
                and isinstance(user_input[CONF_LIMIT], float)
                and not user_input[CONF_LIMIT].is_integer()
            ):
                errors["base"] = "limit_not_an_integer"
            elif (
                CONF_PAGE in user_input
                and isinstance(user_input[CONF_PAGE], float)
                and not user_input[CONF_PAGE].is_integer()
            ):
                errors["base"] = "page_not_an_integer"
            else:
                session = async_get_clientsession(self.hass)
                opendata = OpendataTransport(
                    user_input[CONF_START], user_input[CONF_DESTINATION], session
                )
                if (
                    CONF_OFFSET in user_input
                    and CONF_DATE not in user_input
                    and CONF_TIME not in user_input
                ):
                    offset_opendata(
                        opendata,
                        dict_duration_to_str_duration(user_input[CONF_OFFSET]),
                    )

                try:
                    await opendata.async_get_data()
                except OpendataTransportConnectionError:
                    errors["base"] = "cannot_connect"
                except OpendataTransportError:
                    errors["base"] = "bad_config"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unknown error")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=entry_title_from_config(user_input),
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_input: dict[str, Any]) -> FlowResult:
        """Async import step to set up the connection."""
        self._async_abort_entries_match(import_input)

        if CONF_VIA in import_input and len(import_input[CONF_VIA]) > MAX_VIA:
            return self.async_abort(reason="too_many_via_stations")
        if (
            CONF_LIMIT in import_input
            and isinstance(import_input[CONF_LIMIT], float)
            and not import_input[CONF_LIMIT].is_integer()
        ):
            return self.async_abort(reason="limit_not_an_integer")
        if (
            CONF_PAGE in import_input
            and isinstance(import_input[CONF_PAGE], float)
            and not import_input[CONF_PAGE].is_integer()
        ):
            return self.async_abort(reason="page_not_an_integer")

        session = async_get_clientsession(self.hass)
        opendata = OpendataTransport(
            import_input[CONF_START], import_input[CONF_DESTINATION], session
        )
        if (
            CONF_OFFSET in import_input
            and CONF_DATE not in import_input
            and CONF_TIME not in import_input
        ):
            offset_opendata(
                opendata, dict_duration_to_str_duration(import_input[CONF_OFFSET])
            )

        try:
            await opendata.async_get_data()
        except OpendataTransportConnectionError:
            return self.async_abort(reason="cannot_connect")
        except OpendataTransportError:
            return self.async_abort(reason="bad_config")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error(
                "Unknown error raised by python-opendata-transport for '%s %s', check at http://transport.opendata.ch/examples/stationboard.html if your station names and your parameters are valid",
                import_input[CONF_START],
                import_input[CONF_DESTINATION],
            )
            return self.async_abort(reason="unknown")

        return self.async_create_entry(
            title=import_input[CONF_NAME],
            data=import_input,
        )
