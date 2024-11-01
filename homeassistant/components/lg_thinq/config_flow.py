"""Config flow for LG ThinQ."""

from __future__ import annotations

import logging
from typing import Any
import uuid

from thinqconnect import ThinQApi, ThinQAPIException
from thinqconnect.country import Country
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_COUNTRY
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import CountrySelector, CountrySelectorConfig

from .const import (
    CLIENT_PREFIX,
    CONF_CONNECT_CLIENT_ID,
    DEFAULT_COUNTRY,
    DOMAIN,
    THINQ_DEFAULT_NAME,
    THINQ_PAT_URL,
)

SUPPORTED_COUNTRIES = [country.value for country in Country]

_LOGGER = logging.getLogger(__name__)


class ThinQFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def _get_default_country_code(self) -> str:
        """Get the default country code based on config."""
        country = self.hass.config.country
        if country is not None and country in SUPPORTED_COUNTRIES:
            return country

        return DEFAULT_COUNTRY

    async def _validate_and_create_entry(
        self, access_token: str, country_code: str
    ) -> ConfigFlowResult:
        """Create an entry for the flow."""
        connect_client_id = f"{CLIENT_PREFIX}-{uuid.uuid4()!s}"

        # To verify PAT, create an api to retrieve the device list.
        await ThinQApi(
            session=async_get_clientsession(self.hass),
            access_token=access_token,
            country_code=country_code,
            client_id=connect_client_id,
        ).async_get_device_list()

        # If verification is success, create entry.
        return self.async_create_entry(
            title=THINQ_DEFAULT_NAME,
            data={
                CONF_ACCESS_TOKEN: access_token,
                CONF_CONNECT_CLIENT_ID: connect_client_id,
                CONF_COUNTRY: country_code,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            access_token = user_input[CONF_ACCESS_TOKEN]
            country_code = user_input[CONF_COUNTRY]

            # Check if PAT is already configured.
            await self.async_set_unique_id(access_token)
            self._abort_if_unique_id_configured()

            try:
                return await self._validate_and_create_entry(access_token, country_code)
            except ThinQAPIException:
                errors["base"] = "token_unauthorized"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): cv.string,
                    vol.Required(
                        CONF_COUNTRY, default=self._get_default_country_code()
                    ): CountrySelector(
                        CountrySelectorConfig(countries=SUPPORTED_COUNTRIES)
                    ),
                }
            ),
            description_placeholders={"pat_url": THINQ_PAT_URL},
            errors=errors,
        )
