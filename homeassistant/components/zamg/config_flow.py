"""Config Flow for zamg the Austrian "Zentralanstalt für Meteorologie und Geodynamik" integration."""
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_STATION_ID, DOMAIN, LOGGER
from .sensor import ZamgData, closest_station


class ZamgConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for zamg integration."""

    VERSION = 1

    _client: ZamgData

    def _show_setup_form(self, user_input=None, errors=None, station_id: str = ""):
        """Show the setup form to the user."""
        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STATION_ID,
                        default=user_input.get(CONF_STATION_ID, station_id),
                    ): str
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        station_id = await self.hass.async_add_executor_job(
            closest_station,
            self.hass.config.latitude,
            self.hass.config.longitude,
            self.hass.config.config_dir,
        )

        if user_input is None:
            return self._show_setup_form(user_input, errors, station_id)

        station_id = user_input[CONF_STATION_ID]

        try:
            self._client = ZamgData(station_id)
            await self.hass.async_add_executor_job(self._client.update)
        except (ValueError, TypeError) as err:
            LOGGER.error("Config_flow: Received error from ZAMG: %s", err)
            return self.async_abort(reason="unknown")

        # Check if already configured
        await self.async_set_unique_id(station_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self._client.get_data("station_name"),
            data={CONF_STATION_ID: station_id},
        )

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Handle Nanoleaf configuration import."""
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
