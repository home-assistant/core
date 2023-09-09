"""Config flow for World Air Quality Index (WAQI) integration."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import Any

from aiowaqi import (
    WAQIAirQuality,
    WAQIAuthenticationError,
    WAQIClient,
    WAQIConnectionError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_METHOD,
    CONF_NAME,
)
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.selector import (
    LocationSelector,
    SelectSelector,
    SelectSelectorConfig,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_STATION_NUMBER, DOMAIN, ISSUE_PLACEHOLDER

_LOGGER = logging.getLogger(__name__)

CONF_MAP = "map"


class WAQIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for World Air Quality Index (WAQI)."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            async with WAQIClient(
                session=async_get_clientsession(self.hass)
            ) as waqi_client:
                waqi_client.authenticate(user_input[CONF_API_KEY])
                try:
                    await waqi_client.get_by_ip()
                except WAQIAuthenticationError:
                    errors["base"] = "invalid_auth"
                except WAQIConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception as exc:  # pylint: disable=broad-except
                    _LOGGER.exception(exc)
                    errors["base"] = "unknown"
                else:
                    self.data = user_input
                    if user_input[CONF_METHOD] == CONF_MAP:
                        return await self.async_step_map()
                    return await self.async_step_station_number()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_METHOD): SelectSelector(
                        SelectSelectorConfig(
                            options=[CONF_MAP, CONF_STATION_NUMBER],
                            translation_key="method",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def _async_base_step(
        self,
        step_id: str,
        method: Callable[[WAQIClient, dict[str, Any]], Awaitable[WAQIAirQuality]],
        data_schema: vol.Schema,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            async with WAQIClient(
                session=async_get_clientsession(self.hass)
            ) as waqi_client:
                waqi_client.authenticate(self.data[CONF_API_KEY])
                try:
                    measuring_station = await method(waqi_client, user_input)
                except WAQIConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception as exc:  # pylint: disable=broad-except
                    _LOGGER.exception(exc)
                    errors["base"] = "unknown"
                else:
                    return await self._async_create_entry(measuring_station)
        return self.async_show_form(
            step_id=step_id, data_schema=data_schema, errors=errors
        )

    async def async_step_map(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add measuring station via map."""
        return await self._async_base_step(
            CONF_MAP,
            lambda waqi_client, data: waqi_client.get_by_coordinates(
                data[CONF_LOCATION][CONF_LATITUDE], data[CONF_LOCATION][CONF_LONGITUDE]
            ),
            self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_LOCATION,
                        ): LocationSelector(),
                    }
                ),
                {
                    CONF_LOCATION: {
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    }
                },
            ),
            user_input,
        )

    async def async_step_station_number(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add measuring station via station number."""
        return await self._async_base_step(
            CONF_STATION_NUMBER,
            lambda waqi_client, data: waqi_client.get_by_station_number(
                data[CONF_STATION_NUMBER]
            ),
            vol.Schema(
                {
                    vol.Required(
                        CONF_STATION_NUMBER,
                    ): int,
                }
            ),
            user_input,
        )

    async def _async_create_entry(
        self, measuring_station: WAQIAirQuality
    ) -> FlowResult:
        await self.async_set_unique_id(str(measuring_station.station_id))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=measuring_station.city.name,
            data={
                CONF_API_KEY: self.data[CONF_API_KEY],
                CONF_STATION_NUMBER: measuring_station.station_id,
            },
        )

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Handle importing from yaml."""
        await self.async_set_unique_id(str(import_config[CONF_STATION_NUMBER]))
        try:
            self._abort_if_unique_id_configured()
        except AbortFlow as exc:
            async_create_issue(
                self.hass,
                DOMAIN,
                "deprecated_yaml_import_issue_already_configured",
                breaks_in_ha_version="2024.2.0",
                is_fixable=False,
                severity=IssueSeverity.ERROR,
                translation_key="deprecated_yaml_import_issue_already_configured",
                translation_placeholders=ISSUE_PLACEHOLDER,
            )
            raise exc

        return self.async_create_entry(
            title=import_config[CONF_NAME],
            data={
                CONF_API_KEY: import_config[CONF_API_KEY],
                CONF_STATION_NUMBER: import_config[CONF_STATION_NUMBER],
            },
        )
