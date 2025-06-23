"""Config Flow for Tesla Fleet integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
import re
from typing import Any, cast

import jwt
from tesla_fleet_api import TeslaFleetApi
from tesla_fleet_api.const import SERVERS
from tesla_fleet_api.exceptions import (
    InvalidResponse,
    PreconditionFailed,
    TeslaFleetError,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    QrCodeSelector,
    QrCodeSelectorConfig,
    QrErrorCorrectionLevel,
)

from .const import CONF_DOMAIN, DOMAIN, LOGGER
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
        self.registration_status: dict[str, bool] = {}
        self.tesla_apis: dict[str, TeslaFleetApi] = {}
        self.failed_regions: list[str] = []
        self.data: dict[str, Any] = {}
        self.uid: str | None = None
        self.api: TeslaFleetApi | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return LOGGER

    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle OAuth completion and proceed to domain registration."""
        token = jwt.decode(
            data["token"]["access_token"], options={"verify_signature": False}
        )

        self.data = data
        self.uid = token["sub"]
        server = SERVERS[token["ou_code"].lower()]

        await self.async_set_unique_id(self.uid)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="reauth_account_mismatch")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )
        self._abort_if_unique_id_configured()

        # OAuth done, setup a Partner API connection
        implementation = cast(TeslaUserImplementation, self.flow_impl)

        session = async_get_clientsession(self.hass)
        self.api = TeslaFleetApi(
            session=session,
            server=server,
            partner_scope=True,
            charging_scope=False,
            energy_scope=False,
            user_scope=False,
            vehicle_scope=False,
        )
        await self.api.get_private_key(self.hass.config.path("tesla_fleet.key"))
        await self.api.partner_login(
            implementation.client_id, implementation.client_secret
        )

        return await self.async_step_domain_input()

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
        """Handle domain registration for both regions."""

        assert self.api
        assert self.api.private_key
        assert self.domain

        errors = {}
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
        except InvalidResponse:
            errors["base"] = "invalid_response"
        except TeslaFleetError as e:
            errors["base"] = "unknown_error"
            description_placeholders["error"] = e.message
        else:
            # Get public key from response
            registered_public_key = register_response.get("response", {}).get(
                "public_key"
            )

            if not registered_public_key:
                errors["base"] = "public_key_not_found"
            elif (
                registered_public_key.lower()
                != self.api.public_uncompressed_point.lower()
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
        domain_pattern = re.compile(r"^(?:[a-zA-Z0-9]+\.)+[a-zA-Z0-9-]+$")
        return bool(domain_pattern.match(domain))
