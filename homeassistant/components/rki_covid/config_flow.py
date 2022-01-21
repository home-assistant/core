"""Make the component configurable via the UI."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import async_timeout
from rki_covid_parser.parser import RkiCovidParser
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ATTR_COUNTY, DOMAIN
from .data import accumulate_country, accumulate_district, accumulate_state

_LOGGER = logging.getLogger(__name__)


class RKICovidNumbersConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """RKI Covid numbers config flow."""

    VERSION = 1

    _options: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Invoke when a user initiates a flow via the user interface."""
        _LOGGER.debug("User triggered configuration flow: %s", user_input)

        errors: dict[str, str] = {}

        if self._options is None:
            self._options = {}

            # add items from rki-covid-parser
            session = async_get_clientsession(self.hass)
            parser = RkiCovidParser(session)

            items = {}
            try:
                with async_timeout.timeout(30):
                    await parser.load_data()

                    # country
                    items["Deutschland"] = accumulate_country(parser.country)

                    # states
                    for stat in sorted(
                        parser.states.values(), key=lambda state: state.name
                    ):
                        state = parser.states[stat.name]
                        name = "BL " + state.name
                        items[name] = accumulate_state(name, state)

                    # districts
                    for dist in sorted(
                        parser.districts.values(), key=lambda di: di.name
                    ):
                        district = parser.districts[dist.id]
                        items[district.county] = accumulate_district(district)

                    for case in items.values():
                        self._options[str(case.county)] = case.county

            except asyncio.TimeoutError:
                errors["base"] = "timeout_error"

            except aiohttp.ClientError:
                errors["base"] = "client_error"

        if user_input is not None:
            await self.async_set_unique_id(user_input[ATTR_COUNTY])
            self._abort_if_unique_id_configured()

            # User is done adding sensors, create the config entry.
            return self.async_create_entry(
                title=self._options[user_input[ATTR_COUNTY]], data=user_input
            )

        # Show user input for adding sensors.
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(ATTR_COUNTY): vol.In(self._options)}),
            errors=errors,
        )
