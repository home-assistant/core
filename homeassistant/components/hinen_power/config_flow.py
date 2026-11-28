"""Config flow for Hinen Power integration."""

import logging
from typing import Any, override

from hinen_open_api import HinenOpen, HinenPublic
from hinen_open_api.exceptions import ForbiddenError, HinenAPIError
from probatio import In, Required, Schema

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_TOKEN,
)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import CountrySelector, CountrySelectorConfig

from . import application_credentials
from .auth_config import HinenImplementation
from .const import (
    ATTR_ACCOUNT_ID,
    ATTR_AUTH_LANGUAGE,
    ATTR_REGION_CODE,
    DOMAIN,
    HOST,
    LOGGER,
    SUPPORTED_LANGUAGES,
)

OAUTH_CREDENTIAL_NAME = "Hinen Power"


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle hinen OAuth2 authentication."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize the flow handler."""
        super().__init__()
        self._hinen_open: HinenOpen | None = None
        self._language: str | None = None
        self._region_code: str | None = None

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @override
    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the OAuth2 authentication step."""
        # The flow implementation is built from the application credentials
        # storage. Carry the language and region selected in the user step into
        # it before it is used to build the authorize URL and exchange the
        # authorization code.
        if isinstance(self.flow_impl, HinenImplementation):
            self.flow_impl.language = self._language
            self.flow_impl.region_code = self._region_code
        return await super().async_step_auth(user_input)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the pre-OAuth2 form for credentials, language and region."""
        if user_input is not None:
            # Store the client credentials entered by the user in the
            # application credentials storage, so the auth implementation can
            # be read from there on setup instead of being kept in the entry
            # data.
            credential = ClientCredential(
                user_input[CONF_CLIENT_ID],
                user_input[CONF_CLIENT_SECRET],
                name=OAUTH_CREDENTIAL_NAME,
            )
            await async_import_client_credential(
                self.hass,
                DOMAIN,
                credential,
                DOMAIN,
            )
            self._language = user_input[ATTR_AUTH_LANGUAGE]
            self._region_code = user_input[ATTR_REGION_CODE]
            # Build the flow implementation directly from the entered
            # credentials so the OAuth2 steps use exactly what the user
            # provided.
            self.flow_impl = (
                await application_credentials.async_get_auth_implementation(
                    self.hass,
                    DOMAIN,
                    credential,
                )
            )
            return await self.async_step_auth()

        default_language = SUPPORTED_LANGUAGES[0][0]

        try:
            country_codes = await self._get_country_list()
        except HinenAPIError as ex:
            LOGGER.error("Failed to fetch country list: %s", ex)
            return self.async_abort(reason="failed_to_fetch_countries")

        return self.async_show_form(
            step_id="user",
            data_schema=Schema(
                {
                    Required(ATTR_AUTH_LANGUAGE, default=default_language): In(
                        dict(SUPPORTED_LANGUAGES)
                    ),
                    Required(ATTR_REGION_CODE): CountrySelector(
                        CountrySelectorConfig(countries=country_codes)
                    ),
                    Required(CONF_CLIENT_ID): str,
                    Required(CONF_CLIENT_SECRET): str,
                }
            ),
        )

    async def get_resource(self, token: str, host: str) -> HinenOpen:
        """Get Hinen Open resource async."""
        if self._hinen_open is None:
            self._hinen_open = HinenOpen(
                host, session=async_get_clientsession(self.hass)
            )
            await self._hinen_open.set_user_authentication(token)
        return self._hinen_open

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow, or update existing entry."""
        title = self.flow_impl.name
        try:
            hinen_open = await self.get_resource(
                data[CONF_TOKEN][CONF_ACCESS_TOKEN], data[CONF_TOKEN][HOST]
            )
            device_infos = [
                device_info async for device_info in hinen_open.get_device_infos()
            ]

        except ForbiddenError as ex:
            error = ex.args[0]
            return self.async_abort(
                reason="access_not_configured",
                description_placeholders={"message": error},
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unknown error occurred")
            return self.async_abort(reason="unknown")

        if not device_infos:
            return self.async_abort(reason="no_device")

        await self.async_set_unique_id(str(data[CONF_TOKEN][ATTR_ACCOUNT_ID]))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=title, data=data)

    async def _get_country_list(self) -> list[str]:
        """Fetch the list of countries."""
        hinen_public = HinenPublic(session=async_get_clientsession(self.hass))
        countries = await hinen_public.get_country_list()
        return [country["code"] for country in countries]
