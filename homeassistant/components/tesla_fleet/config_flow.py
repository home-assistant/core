"""Config Flow for Tesla Fleet integration."""

from collections.abc import Mapping
from dataclasses import dataclass
import logging
import re
from typing import Any, cast, override

import jwt
from tesla_fleet_api import TeslaFleetApi
from tesla_fleet_api.const import SERVERS, Scope
from tesla_fleet_api.exceptions import (
    InvalidToken,
    LoginRequired,
    OAuthExpired,
    PreconditionFailed,
    TeslaFleetError,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_DOMAIN
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    QrCodeSelector,
    QrCodeSelectorConfig,
    QrErrorCorrectionLevel,
)

from .const import DOMAIN, LOGGER
from .oauth import TeslaUserImplementation


@dataclass(slots=True)
class RegionRegistrationFailure:
    """Store a normalized regional registration failure."""

    region: str
    reason: str


_REGION_LABELS = {
    "na": "North America",
    "eu": "Europe",
}
_REGION_REASONS = {
    "origin_mismatch": (
        "Verify the entered domain matches the Tesla developer app's allowed origin."
    ),
    "reset_private_key": (
        "Remove `tesla_fleet.key` from your Home Assistant config directory so a "
        "new key pair is generated, then retry registration."
    ),
    "generic": (
        "Tesla rejected the registration in this region. Verify both the hosted "
        "public key and the Tesla developer app configuration, then retry."
    ),
}


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
        self.apis: list[tuple[str, TeslaFleetApi]] = []
        self._region_failures: list[RegionRegistrationFailure] = []
        self._successful_regions: list[str] = []
        self._can_continue_after_region_failures = False

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
        """Handle OAuth completion and proceed to domain registration."""
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

        # OAuth done, setup Partner API connections for all regions
        implementation = cast(TeslaUserImplementation, self.flow_impl)
        session = async_get_clientsession(self.hass)
        failed_regions: list[str] = []

        for region, server_url in SERVERS.items():
            if region == "cn":
                continue
            api = TeslaFleetApi(
                session=session,
                access_token="",
                server=server_url,
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
                    server_url,
                    err,
                )
                return self.async_abort(reason="oauth_error")
            except TeslaFleetError as err:
                LOGGER.warning("Partner login failed for %s: %s", server_url, err)
                failed_regions.append(server_url)
                continue
            self.apis.append((region, api))

        if not self.apis:
            LOGGER.warning(
                "Partner login failed for all regions: %s", ", ".join(failed_regions)
            )
            return self.async_abort(reason="oauth_error")

        if failed_regions:
            LOGGER.warning(
                "Partner login succeeded on some regions but failed on: %s",
                ", ".join(failed_regions),
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

        data_schema = self.add_suggested_values_to_schema(
            vol.Schema({vol.Required(CONF_DOMAIN): str}),
            {CONF_DOMAIN: self.domain} if self.domain else None,
        )

        return self.async_show_form(
            step_id="domain_input",
            description_placeholders={
                "dashboard": "https://developer.tesla.com/en_AU/dashboard/"
            },
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_domain_registration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle domain registration for all regions."""

        assert self.apis
        assert self.apis[0][1].private_key
        assert self.domain

        self._region_failures = []
        self._successful_regions = []
        self._can_continue_after_region_failures = False

        errors: dict[str, str] = {}
        description_placeholders = {
            "public_key_url": f"https://{self.domain}/.well-known/appspecific/com.tesla.3p.public-key.pem",
            "pem": self.apis[0][1].public_pem,
        }

        successful_response: dict[str, Any] | None = None

        for region, api in self.apis:
            try:
                register_response = await api.partner.register(self.domain)
            except TeslaFleetError as err:
                LOGGER.warning(
                    "Partner registration failed for %s (%s) with payload %s",
                    region,
                    api.server,
                    getattr(err, "data", None),
                    exc_info=err,
                )
                self._region_failures.append(
                    RegionRegistrationFailure(
                        region=region,
                        reason=self._classify_region_registration_failure(err),
                    )
                )
            else:
                self._successful_regions.append(region)
                if successful_response is None:
                    successful_response = register_response

        self._can_continue_after_region_failures = bool(
            self._successful_regions and self._region_failures
        )

        if successful_response is None:
            if self._region_failures:
                return await self.async_step_region_failures()
            errors["base"] = "invalid_response"
            return self.async_show_form(
                step_id="domain_registration",
                description_placeholders=description_placeholders,
                errors=errors,
            )

        if self._region_failures:
            LOGGER.warning(
                "Partner registration succeeded on some regions but failed on: %s",
                ", ".join(failure.region for failure in self._region_failures),
            )

        # Verify public key from the successful response
        registered_public_key = successful_response.get("response", {}).get(
            "public_key"
        )

        if not registered_public_key:
            errors["base"] = "public_key_not_found"
        elif (
            registered_public_key.lower()
            != self.apis[0][1].public_uncompressed_point.lower()
        ):
            errors["base"] = "public_key_mismatch"
        elif self._region_failures:
            return await self.async_step_region_failures()
        else:
            return await self.async_step_registration_complete()

        return self.async_show_form(
            step_id="domain_registration",
            description_placeholders=description_placeholders,
            errors=errors,
        )

    async def async_step_region_failures(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Warn about regional partner registration failures."""
        if user_input is not None:
            if self._can_continue_after_region_failures:
                return await self.async_step_registration_complete()
            return await self.async_step_domain_input()

        return self.async_show_form(
            step_id="region_failures",
            data_schema=vol.Schema({}),
            description_placeholders=self._region_failure_placeholders(),
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

    def _classify_region_registration_failure(self, err: TeslaFleetError) -> str:
        """Classify a Tesla registration failure for user guidance."""
        if isinstance(err, PreconditionFailed):
            return "origin_mismatch"

        error_text = " ".join(
            str(part).lower()
            for part in (
                getattr(err, "message", ""),
                getattr(err, "data", ""),
                err,
            )
            if part
        )

        if any(
            marker in error_text
            for marker in ("origin", "allowed origin", "allowed_origin", "domain")
        ):
            return "origin_mismatch"

        if any(
            marker in error_text
            for marker in (
                "public key",
                "public_key",
                "private key",
                "private_key",
                "prime256v1",
                "secp256r1",
            )
        ):
            return "reset_private_key"

        return "generic"

    def _region_failure_placeholders(self) -> dict[str, str]:
        """Build the placeholders for the regional warning step."""
        successful_regions = ""
        if self._successful_regions:
            regions = ", ".join(
                _REGION_LABELS[region] for region in self._successful_regions
            )
            successful_regions = f"Successful regions: {regions}\n"

        failed_regions = ", ".join(
            _REGION_LABELS[region]
            for region in dict.fromkeys(
                failure.region for failure in self._region_failures
            )
        )
        failure_details = "\n".join(
            f"{_REGION_LABELS[failure.region]}: {_REGION_REASONS[failure.reason]}"
            for failure in self._region_failures
        )

        if self._can_continue_after_region_failures:
            next_step = (
                "You can continue setup, but the integration will only be registered "
                "in the successful regions."
            )
        else:
            next_step = (
                "Registration did not succeed in any region. After acknowledging this "
                "warning, you will return to the domain step to retry."
            )

        return {
            "successful_regions": successful_regions,
            "failed_regions": f"Failed regions: {failed_regions}",
            "failure_details": failure_details,
            "next_step": next_step,
        }
