"""Config flow for Entur public transport integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from enturclient import EnturPublicTransportData
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    API_CLIENT_NAME,
    CONF_EXPAND_PLATFORMS,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_STOP_IDS,
    CONF_WHITELIST_LINES,
    DEFAULT_NUMBER_OF_DEPARTURES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STOP_IDS): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, multiple=True)
        ),
        vol.Optional(CONF_EXPAND_PLATFORMS, default=True): BooleanSelector(),
        vol.Optional(CONF_SHOW_ON_MAP, default=False): BooleanSelector(),
        vol.Optional(CONF_WHITELIST_LINES): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, multiple=True)
        ),
        vol.Optional(CONF_OMIT_NON_BOARDING, default=True): BooleanSelector(),
        vol.Optional(
            CONF_NUMBER_OF_DEPARTURES, default=DEFAULT_NUMBER_OF_DEPARTURES
        ): NumberSelector(
            NumberSelectorConfig(min=2, max=10, mode=NumberSelectorMode.SLIDER)
        ),
    }
)


def _parse_stop_ids(stop_ids: list[str]) -> tuple[list[str], list[str]]:
    """Parse stop IDs into stops and quays lists.

    Returns a tuple of (stops, quays).
    """
    stops = [s for s in stop_ids if "StopPlace" in s]
    quays = [s for s in stop_ids if "Quay" in s]
    return stops, quays


async def _validate_whitelist_lines(
    hass: HomeAssistant,
    stops: list[str],
    quays: list[str],
    whitelist: list[str],
    omit_non_boarding: bool,
    number_of_departures: int,
) -> list[str]:
    """Validate that whitelist lines exist at the specified stops.

    Returns a list of invalid line IDs, or empty list if all are valid.
    """
    if not whitelist:
        return []

    # Fetch data without whitelist to get all available lines
    client = EnturPublicTransportData(
        API_CLIENT_NAME,
        stops=stops,
        quays=quays,
        line_whitelist=[],  # No whitelist to get all lines
        omit_non_boarding=omit_non_boarding,
        number_of_departures=number_of_departures,
        web_session=async_get_clientsession(hass),
    )
    await client.update()

    # Collect all available line IDs from all stops/quays
    available_lines: set[str] = set()
    for place_id in client.all_stop_places_quays():
        stop_info = client.get_stop_info(place_id)
        if stop_info and stop_info.estimated_calls:
            for call in stop_info.estimated_calls:
                if call.line_id:
                    available_lines.add(call.line_id)

    # Return lines that don't exist
    return [line for line in whitelist if line not in available_lines]


class EnturConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Entur public transport."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _validate_and_test(
        self, data: dict[str, Any]
    ) -> tuple[list[str], list[str], str | None, list[str] | None]:
        """Validate stop IDs and test connection to Entur API.

        Returns a tuple of (stops, quays, error, invalid_lines).
        Error is None if validation and connection test succeeded.
        invalid_lines contains any whitelist lines that don't exist at the stops.
        """
        stop_ids = data.get(CONF_STOP_IDS, [])
        stops, quays = _parse_stop_ids(stop_ids)

        if not stops and not quays:
            return stops, quays, "invalid_stop_id", None

        omit_non_boarding = data.get(CONF_OMIT_NON_BOARDING, True)
        number_of_departures = data.get(
            CONF_NUMBER_OF_DEPARTURES, DEFAULT_NUMBER_OF_DEPARTURES
        )
        whitelist = data.get(CONF_WHITELIST_LINES) or []

        try:
            invalid_lines = await _validate_whitelist_lines(
                self.hass,
                stops,
                quays,
                whitelist,
                omit_non_boarding,
                number_of_departures,
            )
            if invalid_lines:
                return stops, quays, "invalid_line", invalid_lines
        except (TimeoutError, ClientError):
            return stops, quays, "cannot_connect", None
        except Exception:  # noqa: BLE001
            return stops, quays, "unknown", None

        return stops, quays, None, None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            stop_ids = user_input.get(CONF_STOP_IDS, [])
            _, _, error, invalid_lines = await self._validate_and_test(user_input)

            if error:
                errors["base"] = error
                if invalid_lines:
                    description_placeholders["invalid_lines"] = ", ".join(invalid_lines)
            else:
                unique_id = "_".join(sorted(stop_ids))
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                title = f"Entur {stop_ids[0]}" if stop_ids else "Entur"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders=description_placeholders or None,
        )

    async def async_step_import(self, import_data: ConfigType) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        _LOGGER.debug("Importing Entur config from YAML: %s", import_data)

        stop_ids: list[str] = import_data.get(CONF_STOP_IDS, [])

        unique_id = "_".join(sorted(stop_ids))
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        _, _, error, invalid_lines = await self._validate_and_test(dict(import_data))

        if error:
            if invalid_lines:
                _LOGGER.error(
                    "Failed to import Entur config from YAML (%s): %s. Invalid lines: %s",
                    error,
                    import_data,
                    invalid_lines,
                )
            else:
                _LOGGER.error(
                    "Failed to import Entur config from YAML (%s): %s",
                    error,
                    import_data,
                )
            return self.async_abort(reason=error)

        entry_data = {
            CONF_STOP_IDS: stop_ids,
            CONF_EXPAND_PLATFORMS: import_data.get(CONF_EXPAND_PLATFORMS, True),
            CONF_SHOW_ON_MAP: import_data.get(CONF_SHOW_ON_MAP, False),
            CONF_WHITELIST_LINES: import_data.get(CONF_WHITELIST_LINES, []),
            CONF_OMIT_NON_BOARDING: import_data.get(CONF_OMIT_NON_BOARDING, True),
            CONF_NUMBER_OF_DEPARTURES: import_data.get(
                CONF_NUMBER_OF_DEPARTURES, DEFAULT_NUMBER_OF_DEPARTURES
            ),
        }

        title = import_data.get(
            CONF_NAME, f"Entur {stop_ids[0]}" if stop_ids else "Entur"
        )

        return self.async_create_entry(title=title, data=entry_data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> EnturOptionsFlow:
        """Return the options flow handler."""
        return EnturOptionsFlow()


class EnturOptionsFlow(OptionsFlow):
    """Handle options flow for Entur public transport."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        # Merge data and options for defaults
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            # Validate whitelist lines if provided
            whitelist = user_input.get(CONF_WHITELIST_LINES) or []
            if whitelist:
                stop_ids = self.config_entry.data.get(CONF_STOP_IDS, [])
                stops, quays = _parse_stop_ids(stop_ids)

                try:
                    invalid_lines = await _validate_whitelist_lines(
                        self.hass,
                        stops,
                        quays,
                        whitelist,
                        user_input.get(CONF_OMIT_NON_BOARDING, True),
                        user_input.get(
                            CONF_NUMBER_OF_DEPARTURES, DEFAULT_NUMBER_OF_DEPARTURES
                        ),
                    )
                    if invalid_lines:
                        errors["base"] = "invalid_line"
                        description_placeholders["invalid_lines"] = ", ".join(
                            invalid_lines
                        )
                except (TimeoutError, ClientError):
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_EXPAND_PLATFORMS,
                    default=current.get(CONF_EXPAND_PLATFORMS, True),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_SHOW_ON_MAP,
                    default=current.get(CONF_SHOW_ON_MAP, False),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_WHITELIST_LINES,
                    default=current.get(CONF_WHITELIST_LINES, []),
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT, multiple=True)
                ),
                vol.Optional(
                    CONF_OMIT_NON_BOARDING,
                    default=current.get(CONF_OMIT_NON_BOARDING, True),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_NUMBER_OF_DEPARTURES,
                    default=current.get(
                        CONF_NUMBER_OF_DEPARTURES, DEFAULT_NUMBER_OF_DEPARTURES
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(min=2, max=10, mode=NumberSelectorMode.SLIDER)
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
            description_placeholders=description_placeholders or None,
        )
