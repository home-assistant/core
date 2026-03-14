"""Config flow for Met Office Weather Warnings."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import BASE_URL, CONF_REGION, DOMAIN, REGIONS

_LOGGER = logging.getLogger(__name__)


class MetOfficeWarningsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Met Office Weather Warnings."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            region = user_input[CONF_REGION]

            await self.async_set_unique_id(region)
            self._abort_if_unique_id_configured()

            url = BASE_URL.format(region=region)
            try:
                session = async_get_clientsession(self.hass)
                resp = await session.get(url, timeout=aiohttp.ClientTimeout(total=10))
                resp.raise_for_status()
            except aiohttp.ClientError, TimeoutError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=REGIONS[region],
                    data={CONF_REGION: region},
                )

        options = [
            SelectOptionDict(value=code, label=name) for code, name in REGIONS.items()
        ]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REGION): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )
