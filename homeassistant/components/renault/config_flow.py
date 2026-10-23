"""Config flow to configure Renault component."""

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any, override

import aiohttp
import probatio
from renault_api.const import AVAILABLE_LOCALES
from renault_api.gigya.exceptions import (
    GigyaException,
    InvalidVerificationCodeException,
    PendingTwoFactorAuthenticationException,
)

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_CODE, CONF_EMAIL
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import DOMAIN, RenaultConfigurationKeys
from .renault_hub import RenaultHub

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(RenaultConfigurationKeys.LOCALE): probatio.In(
            AVAILABLE_LOCALES.keys()
        ),
        probatio.Required(RenaultConfigurationKeys.USERNAME): str,
        probatio.Required(RenaultConfigurationKeys.PASSWORD): str,
    }
)
REAUTH_SCHEMA = probatio.Schema(
    {probatio.Required(RenaultConfigurationKeys.PASSWORD): str}
)
TWO_FACTOR_CODE_SCHEMA = probatio.Schema({probatio.Required(CONF_CODE): str})


class RenaultFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Renault config flow."""

    renault_hub: RenaultHub

    def __init__(self) -> None:
        """Initialize the Renault config flow."""
        self.renault_config: dict[str, Any] = {}
        self._two_factor_emails: dict[str, str] = {}
        self._two_factor_email: str = ""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a Renault config flow start.

        Ask the user for API keys.
        """
        errors: dict[str, str] = {}
        suggested_values: Mapping[str, Any] | None = None
        if user_input:
            locale = user_input[RenaultConfigurationKeys.LOCALE]
            self.renault_config.update(user_input)
            self.renault_config.update(AVAILABLE_LOCALES[locale])
            self.renault_hub = RenaultHub(self.hass, locale)
            if self.source == SOURCE_RECONFIGURE:
                self.renault_hub.set_device_ids(
                    self._get_reconfigure_entry().data.get(
                        RenaultConfigurationKeys.DEVICE_IDS, {}
                    )
                )
            try:
                login_success = await self.renault_hub.attempt_login(
                    user_input[RenaultConfigurationKeys.USERNAME],
                    user_input[RenaultConfigurationKeys.PASSWORD],
                )
            except PendingTwoFactorAuthenticationException:
                return await self.async_step_two_factor_email()
            except aiohttp.ClientError, GigyaException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if login_success:
                    return await self._async_login_complete()
                errors["base"] = "invalid_credentials"
            suggested_values = user_input
        elif self.source == SOURCE_RECONFIGURE:
            suggested_values = self._get_reconfigure_entry().data

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    async def async_step_kamereon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select Kamereon account."""
        if user_input:
            await self.async_set_unique_id(
                user_input[RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID]
            )
            if self.source == SOURCE_RECONFIGURE:
                self._abort_if_unique_id_mismatch()
                self.renault_config.update(user_input)
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=self.renault_config,
                )

            self._abort_if_unique_id_configured()

            self.renault_config.update(user_input)
            return self.async_create_entry(
                title=user_input[RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID],
                data=self.renault_config,
            )

        accounts = await self.renault_hub.get_account_ids()
        if len(accounts) == 0:
            return self.async_abort(reason="kamereon_no_account")
        if len(accounts) == 1:
            return await self.async_step_kamereon(
                user_input={RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID: accounts[0]}
            )

        return self.async_show_form(
            step_id="kamereon",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID
                    ): probatio.In(accounts)
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input:
            self.renault_config.update(user_input)
            self.renault_hub = RenaultHub(
                self.hass, reauth_entry.data[RenaultConfigurationKeys.LOCALE]
            )
            self.renault_hub.set_device_ids(
                reauth_entry.data.get(RenaultConfigurationKeys.DEVICE_IDS, {})
            )
            try:
                login_success = await self.renault_hub.attempt_login(
                    reauth_entry.data[RenaultConfigurationKeys.USERNAME],
                    user_input[RenaultConfigurationKeys.PASSWORD],
                )
            except PendingTwoFactorAuthenticationException:
                return await self.async_step_two_factor_email()
            except aiohttp.ClientError, GigyaException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if login_success:
                    return await self._async_login_complete()
                errors["base"] = "invalid_credentials"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={
                RenaultConfigurationKeys.USERNAME: reauth_entry.data[
                    RenaultConfigurationKeys.USERNAME
                ]
            },
        )

    async def async_step_two_factor_email(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the email address to send the two-factor authentication code to."""
        if user_input:
            return await self._async_request_two_factor_auth_code(
                user_input[CONF_EMAIL]
            )

        try:
            emails = await self.renault_hub.get_two_factor_auth_emails()
        except aiohttp.ClientError, GigyaException:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")
        self._two_factor_emails = {
            email.id: email.obfuscated or email.id for email in emails if email.id
        }
        if not self._two_factor_emails:
            return self.async_abort(reason="two_factor_no_email")
        if len(self._two_factor_emails) == 1:
            return await self._async_request_two_factor_auth_code(
                next(iter(self._two_factor_emails))
            )

        return self.async_show_form(
            step_id="two_factor_email",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_EMAIL): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=email_id, label=email)
                                for email_id, email in self._two_factor_emails.items()
                            ]
                        )
                    )
                }
            ),
        )

    async def _async_request_two_factor_auth_code(
        self, email_id: str
    ) -> ConfigFlowResult:
        """Email the two-factor authentication code."""
        try:
            await self.renault_hub.request_two_factor_auth_code(email_id)
        except aiohttp.ClientError, GigyaException:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")
        self._two_factor_email = self._two_factor_emails[email_id]
        return await self.async_step_two_factor_code()

    async def async_step_two_factor_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Complete the login with the two-factor authentication code."""
        errors: dict[str, str] = {}
        if user_input:
            try:
                await self.renault_hub.complete_two_factor_auth(user_input[CONF_CODE])
            except InvalidVerificationCodeException:
                errors["base"] = "invalid_code"
            # Other failures may discard the pending login, so the code can't be retried.
            except aiohttp.ClientError, GigyaException:
                return self.async_abort(reason="cannot_connect")
            except Exception:
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")
            else:
                return await self._async_login_complete()

        return self.async_show_form(
            step_id="two_factor_code",
            data_schema=TWO_FACTOR_CODE_SCHEMA,
            errors=errors,
            description_placeholders={CONF_EMAIL: self._two_factor_email},
        )

    async def _async_login_complete(self) -> ConfigFlowResult:
        """Store the login token and device ids once logged in."""
        if TYPE_CHECKING:
            assert self.renault_hub.login_token
        self.renault_config[RenaultConfigurationKeys.LOGIN_TOKEN] = (
            self.renault_hub.login_token
        )
        self.renault_config[RenaultConfigurationKeys.DEVICE_IDS] = (
            self.renault_hub.device_ids
        )
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=self.renault_config
            )
        return await self.async_step_kamereon()

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user()
