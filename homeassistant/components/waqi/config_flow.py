"""Config flow for World Air Quality Index (WAQI) integration."""
from __future__ import annotations

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
    CONF_NAME,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.selector import LocationSelector
from homeassistant.helpers.typing import ConfigType

from .const import CONF_STATION_NUMBER, DOMAIN, ISSUE_PLACEHOLDER

_LOGGER = logging.getLogger(__name__)


class WAQIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for World Air Quality Index (WAQI)."""

    VERSION = 1

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
                location = user_input[CONF_LOCATION]
                try:
                    measuring_station: WAQIAirQuality = (
                        await waqi_client.get_by_coordinates(
                            location[CONF_LATITUDE], location[CONF_LONGITUDE]
                        )
                    )
                except WAQIAuthenticationError:
                    errors["base"] = "invalid_auth"
                except WAQIConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception as exc:  # pylint: disable=broad-except
                    _LOGGER.exception(exc)
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(str(measuring_station.station_id))
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=measuring_station.city.name,
                        data={
                            CONF_API_KEY: user_input[CONF_API_KEY],
                            CONF_STATION_NUMBER: measuring_station.station_id,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_API_KEY): str,
                        vol.Required(
                            CONF_LOCATION,
                        ): LocationSelector(),
                    }
                ),
                user_input
                or {
                    CONF_LOCATION: {
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    }
                },
            ),
            errors=errors,
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
                breaks_in_ha_version="2024.4.0",
                is_fixable=False,
                severity=IssueSeverity.ERROR,
                translation_key="deprecated_yaml_import_issue_already_configured",
                translation_placeholders=ISSUE_PLACEHOLDER,
            )
            raise exc

        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.4.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "World Air Quality Index",
            },
        )
        return self.async_create_entry(
            title=import_config[CONF_NAME],
            data={
                CONF_API_KEY: import_config[CONF_API_KEY],
                CONF_STATION_NUMBER: import_config[CONF_STATION_NUMBER],
            },
        )
