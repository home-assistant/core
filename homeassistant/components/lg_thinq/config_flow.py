"""Config flow for LG ThinQ."""

from collections.abc import Mapping
import logging
from typing import Any, override
import uuid

import probatio
from thinqconnect import ThinQApi, ThinQAPIErrorCodes, ThinQAPIException
from thinqconnect.country import Country

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
THINQ_ERRORS = {
    ThinQAPIErrorCodes.INVALID_TOKEN: "invalid_token",
    ThinQAPIErrorCodes.NOT_ACCEPTABLE_TERMS: "not_acceptable_terms",
    ThinQAPIErrorCodes.NOT_ALLOWED_API_AGAIN: "not_allowed_api_again",
    ThinQAPIErrorCodes.NOT_SUPPORTED_COUNTRY: "not_supported_country",
    ThinQAPIErrorCodes.EXCEEDED_API_CALLS: "exceeded_api_calls",
}

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

    async def _async_validate_access_token(
        self, access_token: str, country_code: str, client_id: str
    ) -> None:
        """Verify the PAT by retrieving the device list."""
        await ThinQApi(
            session=async_get_clientsession(self.hass),
            access_token=access_token,
            country_code=country_code,
            client_id=client_id,
        ).async_get_device_list()

    async def _validate_and_create_entry(
        self, access_token: str, country_code: str
    ) -> ConfigFlowResult:
        """Create an entry for the flow."""
        connect_client_id = f"{CLIENT_PREFIX}-{uuid.uuid4()!s}"

        await self._async_validate_access_token(
            access_token, country_code, connect_client_id
        )

        # If verification is success, create entry.
        return self.async_create_entry(
            title=THINQ_DEFAULT_NAME,
            data={
                CONF_ACCESS_TOKEN: access_token,
                CONF_CONNECT_CLIENT_ID: connect_client_id,
                CONF_COUNTRY: country_code,
            },
        )

    @override
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
            except ThinQAPIException as exc:
                errors["base"] = THINQ_ERRORS.get(exc.code, "token_unauthorized")
                _LOGGER.error("Failed to validate access_token %s", exc)

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(probatio.Secret(CONF_ACCESS_TOKEN)): cv.string,
                    probatio.Required(
                        CONF_COUNTRY, default=self._get_default_country_code()
                    ): CountrySelector(
                        CountrySelectorConfig(countries=SUPPORTED_COUNTRIES)
                    ),
                }
            ),
            description_placeholders={"pat_url": THINQ_PAT_URL},
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the PAT is rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new PAT."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            access_token = user_input[CONF_ACCESS_TOKEN]

            # The PAT is the unique ID, so only reject one used by another entry.
            if access_token != reauth_entry.unique_id:
                await self.async_set_unique_id(access_token)
                self._abort_if_unique_id_configured()

            try:
                await self._async_validate_access_token(
                    access_token,
                    reauth_entry.data[CONF_COUNTRY],
                    reauth_entry.data[CONF_CONNECT_CLIENT_ID],
                )
            except ThinQAPIException as exc:
                errors["base"] = THINQ_ERRORS.get(exc.code, "token_unauthorized")
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    unique_id=access_token,
                    data_updates={CONF_ACCESS_TOKEN: access_token},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_ACCESS_TOKEN)): cv.string}
            ),
            description_placeholders={"pat_url": THINQ_PAT_URL},
            errors=errors,
        )
