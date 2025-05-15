"""Config flow for IMGW-PIB integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from imgw_pib import ImgwPib
from imgw_pib.exceptions import ApiError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_STATION_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ImgwPibFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IMGW-PIB."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        client_session = async_get_clientsession(self.hass)

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]

            await self.async_set_unique_id(station_id, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            try:
                imgwpib = await ImgwPib.create(
                    client_session, hydrological_station_id=station_id
                )
                hydrological_data = await imgwpib.get_hydrological_data()
            except (ClientError, TimeoutError, ApiError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                title = f"{hydrological_data.river} ({hydrological_data.station})"
                return self.async_create_entry(title=title, data=user_input)

        try:
            imgwpib = await ImgwPib.create(client_session)
            await imgwpib.update_hydrological_stations()
        except (ClientError, TimeoutError, ApiError):
            return self.async_abort(reason="cannot_connect")

        options: list[SelectOptionDict] = [
            SelectOptionDict(value=station_id, label=station_name)
            for station_id, station_name in imgwpib.hydrological_stations.items()
        ]

        schema: vol.Schema = vol.Schema(
            {
                vol.Required(CONF_STATION_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=False,
                        sort=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    ),
                )
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
