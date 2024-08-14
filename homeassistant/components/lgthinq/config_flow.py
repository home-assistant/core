"""Config flow for LG ThinQ."""

from __future__ import annotations

import logging
from typing import Any
import uuid

import pycountry
from thinqconnect.thinq_api import ThinQApi
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_COUNTRY, CONF_NAME
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
    TRANSLATION_ERROR_CODE,
)

SUPPORTED_COUNTRIES = [
    SelectOptionDict(value=x.alpha_2, label=x.name) for x in pycountry.countries
]

_LOGGER = logging.getLogger(__name__)


class ThinQFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        super().__init__()
        self._access_token: str = ""
        self._country_code: str = DEFAULT_COUNTRY
        self._entry_name: str = ""

    def _get_default_country_code(self) -> str:
        """Get the default country code based on config."""
        country = self.hass.config.country
        if country is not None:
            for x in SUPPORTED_COUNTRIES:
                if x.get("value") == country:
                    return country

        return DEFAULT_COUNTRY

    async def _validate_and_create_entry(self) -> ConfigFlowResult:
        """Create an entry for the flow."""
        connect_client_id: str = f"{CLIENT_PREFIX}-{uuid.uuid4()!s}"

        # To verify PAT, create an api to retrieve the device list.
        api = ThinQApi(
            session=async_get_clientsession(self.hass),
            access_token=self._access_token,
            country_code=self._country_code,
            client_id=connect_client_id,
        )
        result = await api.async_get_device_list()
        _LOGGER.debug("validate_and_create_entry: %s", result)

        if result.status >= 400:
            # Support translation for TRANSLATION_ERROR_CODE, key is error_code.
            reason_str: str = (
                result.error_code
                if result.error_code in TRANSLATION_ERROR_CODE
                else result.error_message
            )
            return self.async_abort(reason=reason_str)

        # If verification is success, create entry.
        data = {
            CONF_ACCESS_TOKEN: self._access_token,
            CONF_CONNECT_CLIENT_ID: connect_client_id,
            CONF_COUNTRY: self._country_code,
        }
        return self.async_create_entry(title=self._entry_name, data=data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        # Get the PAT(Personal Access Token) and validate it.
        if user_input is None or CONF_ACCESS_TOKEN not in user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ACCESS_TOKEN): cv.string,
                        vol.Optional(CONF_NAME, default=THINQ_DEFAULT_NAME): cv.string,
                    }
                ),
                description_placeholders={
                    "pat_url": THINQ_PAT_URL,
                },
            )

        self._access_token = str(user_input.get(CONF_ACCESS_TOKEN, ""))
        self._entry_name = str(user_input.get(CONF_NAME, ""))

        # Check if PAT is already configured.
        await self.async_set_unique_id(self._access_token)
        self._abort_if_unique_id_configured()

        return await self.async_step_region()

    async def async_step_region(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the seleting the country and language."""
        if user_input is None:
            return self.async_show_form(
                step_id="region",
                data_schema=vol.Schema(
                    {
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
            )

        self._country_code = str(user_input.get(CONF_COUNTRY, DEFAULT_COUNTRY))
        return await self._validate_and_create_entry()
