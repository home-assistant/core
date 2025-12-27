"""Config flow for Entur public transport integration."""

from __future__ import annotations

import logging
from random import randint
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
from homeassistant.core import callback
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
        vol.Optional(CONF_WHITELIST_LINES, default=[]): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, multiple=True)
        ),
        vol.Optional(CONF_OMIT_NON_BOARDING, default=True): BooleanSelector(),
        vol.Optional(CONF_NUMBER_OF_DEPARTURES, default=2): NumberSelector(
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


class EnturConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Entur public transport."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _validate_and_test(
        self, data: dict[str, Any]
    ) -> tuple[list[str], list[str], str | None]:
        """Validate stop IDs and test connection to Entur API.

        Returns a tuple of (stops, quays, error).
        Error is None if validation and connection test succeeded.
        """
        stop_ids = data.get(CONF_STOP_IDS, [])
        stops, quays = _parse_stop_ids(stop_ids)

        if not stops and not quays:
            return stops, quays, "invalid_stop_id"

        omit_non_boarding = data.get(CONF_OMIT_NON_BOARDING, True)
        number_of_departures = data.get(CONF_NUMBER_OF_DEPARTURES, 2)

        try:
            client = EnturPublicTransportData(
                API_CLIENT_NAME.format(str(randint(100000, 999999))),
                stops=stops,
                quays=quays,
                line_whitelist=[],
                omit_non_boarding=omit_non_boarding,
                number_of_departures=number_of_departures,
                web_session=async_get_clientsession(self.hass),
            )
            await client.update()
        except (TimeoutError, ClientError):
            return stops, quays, "cannot_connect"
        except Exception:  # noqa: BLE001
            return stops, quays, "unknown"

        return stops, quays, None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            stop_ids = user_input.get(CONF_STOP_IDS, [])
            _, _, error = await self._validate_and_test(user_input)

            if error:
                errors["base"] = error
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
        )

    async def async_step_import(self, import_data: ConfigType) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        _LOGGER.debug("Importing Entur config from YAML: %s", import_data)

        stop_ids: list[str] = import_data.get(CONF_STOP_IDS, [])

        unique_id = "_".join(sorted(stop_ids))
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        _, _, error = await self._validate_and_test(dict(import_data))

        if error:
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
            CONF_NUMBER_OF_DEPARTURES: import_data.get(CONF_NUMBER_OF_DEPARTURES, 2),
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
        # Merge data and options for defaults
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
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
                    default=current.get(CONF_NUMBER_OF_DEPARTURES, 2),
                ): NumberSelector(
                    NumberSelectorConfig(min=2, max=10, mode=NumberSelectorMode.SLIDER)
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
