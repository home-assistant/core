"""Config Flow for zamg the Austrian "Zentralanstalt für Meteorologie und Geodynamik" integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from zamg import ZamgData

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
            LOGGER.debug("config_flow: created new client")

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
            title=self._client.get_station_name,
            data={CONF_STATION_ID: station_id},
        )

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Handle ZAMG configuration import."""
        self._async_abort_entries_match({CONF_STATION_ID: config[CONF_STATION_ID]})
        LOGGER.debug(
            "Importing zamg on %s from your configuration.yaml", config[CONF_STATION_ID]
        )

        try:
            if self._client is None:
                self._client = ZamgData(config[CONF_STATION_ID])
                self._client.session = async_get_clientsession(self.hass)
            await self._client.update()
        except (ValueError, TypeError) as err:
            LOGGER.error("Received error from ZAMG: %s", err)
            return self.async_abort(reason="unknown")

        return self.async_create_entry(
            title=self._client.get_station_name,
            data={CONF_STATION_ID: config[CONF_STATION_ID]},
        )
