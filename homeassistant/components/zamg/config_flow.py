"""Config Flow for zamg the Austrian "Zentralanstalt für Meteorologie und Geodynamik" integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from zamg import ZamgData

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_STATION_ID, DOMAIN, LOGGER


class ZamgConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for zamg integration."""

    VERSION = 1

    _client: ZamgData | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, Any] = {}

        if self._client is None:
            self._client = ZamgData()
            self._client.session = async_get_clientsession(self.hass)

        if user_input is None:
            closest_station_id = await self._client.closest_station(
                self.hass.config.latitude,
                self.hass.config.longitude,
            )
            LOGGER.debug("config_flow: closest station = %s", str(closest_station_id))
            stations = await self._client.zamg_stations()
            user_input = {}

            schema = vol.Schema(
                {
                    vol.Required(
                        CONF_STATION_ID, default=int(closest_station_id)
                    ): vol.In(
                        {
                            int(station): f"{stations[station][2]} ({station})"
                            for station in stations
                        }
                    )
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema)

        station_id = str(user_input[CONF_STATION_ID])

        # Check if already configured
        await self.async_set_unique_id(station_id)
        self._abort_if_unique_id_configured()

        try:
            self._client.set_default_station(station_id)
            await self._client.update()
        except (ValueError, TypeError) as err:
            LOGGER.error("Config_flow: Received error from ZAMG: %s", err)
            errors["base"] = "cannot_connect"
            return self.async_abort(
                reason="cannot_connect", description_placeholders=errors
            )

        return self.async_create_entry(
            title=user_input.get(CONF_NAME) or self._client.get_station_name,
            data={CONF_STATION_ID: station_id},
        )

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Handle ZAMG configuration import."""
        station_id = str(config.get(CONF_STATION_ID))
        station_name = config.get(CONF_NAME)
        # create issue every time after restart
        # parameter is_persistent seems not working
        async_create_issue(
            self.hass,
            DOMAIN,
            "deprecated_yaml",
            breaks_in_ha_version="2023.1.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
        )

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if station_id in entry.data[CONF_STATION_ID]:
                return self.async_abort(
                    reason="already_configured",
                )

        if self._client is None:
            self._client = ZamgData()
            self._client.session = async_get_clientsession(self.hass)

        if station_id not in await self._client.zamg_stations():
            LOGGER.warning(
                "Configured station_id %s could not be found at zamg, adding the nearest weather station instead",
                station_id,
            )
            latitude = config.get(CONF_LATITUDE) or self.hass.config.latitude
            longitude = config.get(CONF_LONGITUDE) or self.hass.config.longitude
            station_id = await self._client.closest_station(latitude, longitude)

        if not station_name:
            await self._client.zamg_stations()
            self._client.set_default_station(station_id)
            station_name = self._client.get_station_name

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if station_id in entry.data[CONF_STATION_ID]:
                return self.async_abort(
                    reason="already_configured",
                )

        LOGGER.debug(
            "importing zamg station from configuration.yaml: station_id = %s, name = %s",
            station_id,
            station_name,
        )

        return await self.async_step_user(
            user_input={
                CONF_STATION_ID: int(station_id),
                CONF_NAME: station_name,
            }
        )
