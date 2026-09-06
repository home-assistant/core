"""Config Flow for Tesla Fleet integration."""

from collections.abc import Mapping
import logging
import re
from typing import Any, cast, override

import jwt
from tesla_fleet_api import TeslaFleetApi
from tesla_fleet_api.const import Scope
from tesla_fleet_api.exceptions import (
    InvalidToken,
    LoginRequired,
    OAuthExpired,
    PreconditionFailed,
    TeslaFleetError,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_DOMAIN, CONF_REGION
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    QrCodeSelector,
    QrCodeSelectorConfig,
    QrErrorCorrectionLevel,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN, LOGGER, REGION_SERVERS, REGIONS
from .oauth import TeslaUserImplementation


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Tesla Fleet API OAuth2 authentication."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize config flow."""
        super().__init__()
        self.domain: str | None = None
        self.data: dict[str, Any] = {}
        self.uid: str | None = None
        self.region: str = REGIONS[0]
        self.api: TeslaFleetApi | None = None

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return LOGGER

    @override
    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle OAuth completion and proceed to region selection."""
        token = jwt.decode(
            data["token"]["access_token"], options={"verify_signature": False}
        )

        self.data = data
        self.uid = token["sub"]

        await self.async_set_unique_id(self.uid)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="reauth_account_mismatch")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )
        self._abort_if_unique_id_configured()

        # Default the region to the one detected from the OAuth token
        detected = token.get("ou_code", "").lower()
        self.region = detected if detected in REGIONS else REGIONS[0]

        return await self.async_step_region()

    async def async_step_region(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle region selection and partner login."""

        errors: dict[str, str] = {}

        if user_input is not None:
            self.region = user_input[CONF_REGION]

            implementation = cast(TeslaUserImplementation, self.flow_impl)
            session = async_get_clientsession(self.hass)
            api = TeslaFleetApi(
                session=session,
                access_token="",
                server=REGION_SERVERS[self.region],
                partner_scope=True,
                charging_scope=False,
                energy_scope=False,
                user_scope=False,
                vehicle_scope=False,
            )
            await api.get_private_key(self.hass.config.path("tesla_fleet.key"))
            try:
                await api.partner_login(
                    implementation.client_id,
                    implementation.client_secret,
                    [Scope.OPENID],
                )
            except (InvalidToken, OAuthExpired, LoginRequired) as err:
                LOGGER.warning(
                    "Partner login failed for %s due to an authentication error: %s",
                    api.server,
                    err,
                )
                return self.async_abort(reason="oauth_error")
            except TeslaFleetError as err:
                LOGGER.warning("Partner login failed for %s: %s", api.server, err)
                errors["base"] = "cannot_connect"
            else:
                self.api = api
                return await self.async_step_domain_input()

        return self.async_show_form(
            step_id="region",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REGION, default=self.region): SelectSelector(
                        SelectSelectorConfig(
                            options=REGIONS,
                            translation_key="region",
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_domain_input(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Handle domain input step."""

        errors = errors or {}

        if user_input is not None:
            domain = user_input[CONF_DOMAIN].strip().lower()

            # Validate domain format
            if not self._is_valid_domain(domain):
                errors[CONF_DOMAIN] = "invalid_domain"
            else:
                self.domain = domain
                return await self.async_step_domain_registration()

        return self.async_show_form(
            step_id="domain_input",
            description_placeholders={
                "dashboard": "https://developer.tesla.com/en_AU/dashboard/"
            },
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DOMAIN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_domain_registration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle domain registration for the selected region."""

        assert self.api
        assert self.api.private_key
        assert self.domain

        errors: dict[str, str] = {}
        description_placeholders = {
            "public_key_url": f"https://{self.domain}/.well-known/appspecific/com.tesla.3p.public-key.pem",
            "pem": self.api.public_pem,
        }

        try:
            register_response = await self.api.partner.register(self.domain)
        except PreconditionFailed:
            return await self.async_step_domain_input(
                errors={CONF_DOMAIN: "precondition_failed"}
            )
        except TeslaFleetError as e:
            LOGGER.warning(
                "Partner registration failed for %s: %s", self.api.server, e.message
            )
            errors["base"] = "invalid_response"
            return self.async_show_form(
                step_id="domain_registration",
                description_placeholders=description_placeholders,
                errors=errors,
            )

        registered_public_key = register_response.get("response", {}).get("public_key")

        if not registered_public_key:
            errors["base"] = "public_key_not_found"
        elif (
            registered_public_key.lower() != self.api.public_uncompressed_point.lower()
        ):
            errors["base"] = "public_key_mismatch"
        else:
            return await self.async_step_registration_complete()

        return self.async_show_form(
            step_id="domain_registration",
            description_placeholders=description_placeholders,
            errors=errors,
        )

    async def async_step_registration_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show completion and virtual key installation."""
        if user_input is not None and self.uid and self.data:
            return self.async_create_entry(title=self.uid, data=self.data)

        if not self.domain:
            return await self.async_step_domain_input()

        virtual_key_url = f"https://www.tesla.com/_ak/{self.domain}"
        data_schema = vol.Schema({}).extend(
            {
                vol.Optional("qr_code"): QrCodeSelector(
                    config=QrCodeSelectorConfig(
                        data=virtual_key_url,
                        scale=6,
                        error_correction_level=QrErrorCorrectionLevel.QUARTILE,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="registration_complete",
            data_schema=data_schema,
            description_placeholders={
                "virtual_key_url": virtual_key_url,
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={"name": "Tesla Fleet"},
            )
        # For reauth, skip domain registration and go straight to OAuth
        return await super().async_step_user()

    def _is_valid_domain(self, domain: str) -> bool:
        """Validate domain format."""
        # Basic domain validation regex
        domain_pattern = re.compile(
            r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
        )
        return bool(domain_pattern.match(domain))
