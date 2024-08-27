"""Config flow for LG ThinQ."""

from __future__ import annotations

import logging
from typing import Any
import uuid

import pycountry
from thinqconnect import ThinQApi, ThinQAPIException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_COUNTRY
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CLIENT_PREFIX,
    CONF_CONNECT_CLIENT_ID,
    DEFAULT_COUNTRY,
    DOMAIN,
    THINQ_DEFAULT_NAME,
    THINQ_PAT_URL,
)

SUPPORTED_COUNTRIES = [
    SelectOptionDict(value=x.alpha_2, label=x.name) for x in pycountry.countries
]

_LOGGER = logging.getLogger(__name__)


class ThinQFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def _get_default_country_code(self) -> str:
        """Get the default country code based on config."""
        country = self.hass.config.country
        if country is not None:
            for x in SUPPORTED_COUNTRIES:
                if x.get("value") == country:
                    return country

        return DEFAULT_COUNTRY

    async def _validate_and_create_entry(
        self, access_token: str, country_code: str
    ) -> ConfigFlowResult:
        """Create an entry for the flow."""
        connect_client_id = f"{CLIENT_PREFIX}-{uuid.uuid4()!s}"
        try:
            # To verify PAT, create an api to retrieve the device list.
            await ThinQApi(
                session=async_get_clientsession(self.hass),
                access_token=access_token,
                country_code=country_code,
                client_id=connect_client_id,
            ).async_get_device_list()
        except ThinQAPIException as exc:
            return self.async_abort(reason=exc.message)

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
        # Get the PAT(Personal Access Token) and validate it.
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ACCESS_TOKEN): cv.string,
                        vol.Required(
                            CONF_COUNTRY,
                            default=self._get_default_country_code(),
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=SUPPORTED_COUNTRIES,
                                mode=SelectSelectorMode.DROPDOWN,
                                sort=True,
                            )
                        ),
                    }
                ),
                description_placeholders={
                    "pat_url": THINQ_PAT_URL,
                },
            )

        access_token = str(user_input.get(CONF_ACCESS_TOKEN, ""))
        country_code = str(user_input.get(CONF_COUNTRY, DEFAULT_COUNTRY))

        # Check if PAT is already configured.
        await self.async_set_unique_id(access_token)
        self._abort_if_unique_id_configured()

        return await self._validate_and_create_entry(access_token, country_code)
