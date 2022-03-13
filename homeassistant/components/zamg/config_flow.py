"""Config Flow for zamg the Austrian "Zentralanstalt für Meteorologie und Geodynamik" integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_STATION_ID, DOMAIN, LOGGER
from .sensor import ZamgData, closest_station, zamg_stations


class ZamgConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for zamg integration."""

    VERSION = 1

    _client: ZamgData

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle a flow initiated by the user."""
        errors: dict[str, Any] = {}

        if user_input is None:
            closest_station_id = await self.hass.async_add_executor_job(
                closest_station,
                self.hass.config.latitude,
                self.hass.config.longitude,
                self.hass.config.config_dir,
            )
            user_input = {}
            stations = zamg_stations(self.hass.config.config_dir)

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
            self._client = ZamgData(station_id)
            await self.hass.async_add_executor_job(self._client.update)
        except (ValueError, TypeError) as err:
            LOGGER.error("Config_flow: Received error from ZAMG: %s", err)
            errors["base"] = "cannot_connect"
            return self.async_abort(
                reason="cannot_connect", description_placeholders=errors
            )

        return self.async_create_entry(
            title=self._client.get_data("station_name"),
            data={CONF_STATION_ID: station_id},
        )

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Handle ZAMG configuration import."""
        self._async_abort_entries_match({CONF_STATION_ID: config[CONF_STATION_ID]})
        LOGGER.debug(
            "Importing zamg on %s from your configuration.yaml", config[CONF_STATION_ID]
        )

        try:
            self._client = ZamgData(config[CONF_STATION_ID])
            await self.hass.async_add_executor_job(self._client.update)
        except (ValueError, TypeError) as err:
            LOGGER.error("Received error from ZAMG: %s", err)
            return self.async_abort(reason="unknown")

        return self.async_create_entry(
            title=self._client.get_data("station_name"),
            data={CONF_STATION_ID: config[CONF_STATION_ID]},
        )
