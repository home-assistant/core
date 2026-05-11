"""Config flow for Entur public transport integration."""

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
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STOP_IDS): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, multiple=True)
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
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


def _get_invalid_stop_ids(stop_ids: list[str]) -> list[str]:
    """Return the stop IDs that are neither stop places nor quays."""
    return [
        stop_id
        for stop_id in stop_ids
        if "StopPlace" not in stop_id and "Quay" not in stop_id
    ]


def _has_only_valid_stop_ids(stop_ids: list[str]) -> bool:
    """Return True if all provided stop IDs are valid stop places or quays."""
    return not _get_invalid_stop_ids(stop_ids)


class EnturConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Entur public transport."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _validate_and_test(
        self, data: dict[str, Any]
    ) -> tuple[list[str], list[str], str | None, list[str]]:
        """Validate stop IDs and test connection to Entur API.

        Returns a tuple of (stops, quays, error, invalid_stop_ids).
        Error is None if validation and connection test succeeded.
        """
        stop_ids = data.get(CONF_STOP_IDS, [])
        stops, quays = _parse_stop_ids(stop_ids)
        invalid_stop_ids = _get_invalid_stop_ids(stop_ids)

        if not stops and not quays:
            return stops, quays, "invalid_stop_id", invalid_stop_ids

        if not _has_only_valid_stop_ids(stop_ids):
            return stops, quays, "invalid_stop_id", invalid_stop_ids

        omit_non_boarding = data.get(CONF_OMIT_NON_BOARDING, True)
        number_of_departures = data.get(CONF_NUMBER_OF_DEPARTURES, 2)
        line_whitelist = data.get(CONF_WHITELIST_LINES, [])

        try:
            client = EnturPublicTransportData(
                API_CLIENT_NAME.format(str(randint(100000, 999999))),
                stops=stops,
                quays=quays,
                line_whitelist=line_whitelist,
                omit_non_boarding=omit_non_boarding,
                number_of_departures=number_of_departures,
                web_session=async_get_clientsession(self.hass),
            )
            await client.update()
        except TimeoutError:
            return stops, quays, "cannot_connect", invalid_stop_ids
        except ClientError:
            return stops, quays, "cannot_connect", invalid_stop_ids
        except Exception:  # noqa: BLE001
            return stops, quays, "unknown", invalid_stop_ids

        return stops, quays, None, invalid_stop_ids

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        invalid_stop_ids_message = ""

        if user_input is not None:
            stop_ids = user_input.get(CONF_STOP_IDS, [])
            _, _, error, invalid_stop_ids = await self._validate_and_test(user_input)

            if error:
                errors["base"] = error
                if invalid_stop_ids:
                    invalid_stop_ids_message = "\n\nInvalid stop IDs: " + ", ".join(
                        f"`{stop_id}`" for stop_id in invalid_stop_ids
                    )
            else:
                unique_id = "_".join(sorted(stop_ids))
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                title = user_input.get(CONF_NAME, DEFAULT_NAME)
                return self.async_create_entry(
                    title=title,
                    data={CONF_STOP_IDS: stop_ids},
                    options={
                        CONF_EXPAND_PLATFORMS: user_input.get(
                            CONF_EXPAND_PLATFORMS, True
                        ),
                        CONF_SHOW_ON_MAP: user_input.get(CONF_SHOW_ON_MAP, False),
                        CONF_WHITELIST_LINES: user_input.get(CONF_WHITELIST_LINES, []),
                        CONF_OMIT_NON_BOARDING: user_input.get(
                            CONF_OMIT_NON_BOARDING, True
                        ),
                        CONF_NUMBER_OF_DEPARTURES: user_input.get(
                            CONF_NUMBER_OF_DEPARTURES, 2
                        ),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            description_placeholders={
                "entur_url": "https://entur.no/",
                "invalid_stop_ids_message": invalid_stop_ids_message,
            },
            errors=errors,
        )

    async def async_step_import(self, import_data: ConfigType) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        _LOGGER.debug("Importing Entur config from YAML: %s", import_data)

        stop_ids: list[str] = import_data.get(CONF_STOP_IDS, [])

        _, _, error, invalid_stop_ids = await self._validate_and_test(dict(import_data))

        if error:
            _LOGGER.error(
                "Failed to import Entur config from YAML (%s): %s",
                error,
                import_data,
            )
            return self.async_abort(
                reason=error,
                description_placeholders={
                    "invalid_stop_ids": ", ".join(
                        f"`{stop_id}`" for stop_id in invalid_stop_ids
                    )
                },
            )

        unique_id = "_".join(sorted(stop_ids))
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        title = import_data.get(
            CONF_NAME, f"Entur {stop_ids[0]}" if stop_ids else "Entur"
        )

        return self.async_create_entry(
            title=title,
            data={CONF_STOP_IDS: stop_ids},
            options={
                CONF_EXPAND_PLATFORMS: import_data.get(CONF_EXPAND_PLATFORMS, True),
                CONF_SHOW_ON_MAP: import_data.get(CONF_SHOW_ON_MAP, False),
                CONF_WHITELIST_LINES: import_data.get(CONF_WHITELIST_LINES, []),
                CONF_OMIT_NON_BOARDING: import_data.get(CONF_OMIT_NON_BOARDING, True),
                CONF_NUMBER_OF_DEPARTURES: import_data.get(
                    CONF_NUMBER_OF_DEPARTURES, 2
                ),
            },
        )

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
        current = self.config_entry.options

        if user_input is not None:
            return self.async_create_entry(
                data={
                    **user_input,
                    CONF_EXPAND_PLATFORMS: current.get(CONF_EXPAND_PLATFORMS, True),
                }
            )

        options_schema = vol.Schema(
            {
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
