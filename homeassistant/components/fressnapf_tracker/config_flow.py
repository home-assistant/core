"""Config flow for the Fressnapf Tracker integration."""

import asyncio
from collections.abc import Mapping
import logging
from typing import Any, override

from fressnapftracker import (
    AuthClient,
    FressnapfTrackerAuthenticationError,
    FressnapfTrackerConnectionError,
    FressnapfTrackerInvalidPhoneNumberError,
    FressnapfTrackerInvalidTokenError,
)
import probatio

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CUSTOMER_ID,
    CONF_PHONE_NUMBER,
    CONF_SMS_CODE,
    CONF_USER_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

MAGIC_LINK_POLL_INTERVAL = 5
MAGIC_LINK_TIMEOUT = 300

STEP_EMAIL_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
                autocomplete="email",
            )
        ),
        probatio.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)
STEP_SMS_DATA_SCHEMA = probatio.Schema({probatio.Required(CONF_PHONE_NUMBER): str})
STEP_SMS_CODE_DATA_SCHEMA = probatio.Schema({probatio.Required(CONF_SMS_CODE): str})


class FressnapfTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fressnapf Tracker."""

    VERSION = 1

    def __init__(self) -> None:
        """Init Config Flow."""
        self._context: dict[str, Any] = {}
        self._auth_client: AuthClient | None = None
        self._magic_link_task: asyncio.Task[None] | None = None

    @property
    def auth_client(self) -> AuthClient:
        """Return the auth client, creating it if needed."""
        if self._auth_client is None:
            self._auth_client = AuthClient(client=get_async_client(self.hass))
        return self._auth_client

    async def _async_wait_for_magic_link(self) -> None:
        """Wait for the magic link to be opened and complete authentication."""
        async with asyncio.timeout(MAGIC_LINK_TIMEOUT):
            while not await self.auth_client.check_magic_link_was_clicked(
                self._context[CONF_ACCESS_TOKEN]
            ):
                await asyncio.sleep(MAGIC_LINK_POLL_INTERVAL)

            await self.auth_client.complete_magic_link(
                self._context[CONF_USER_ID],
                self._context[CONF_ACCESS_TOKEN],
                self._context[CONF_CUSTOMER_ID],
            )

    async def _async_request_sms_code(
        self, phone_number: str
    ) -> tuple[dict[str, str], bool]:
        """Request SMS code and return errors dict and success flag."""
        errors: dict[str, str] = {}
        try:
            response = await self.auth_client.request_sms_code(
                phone_number=phone_number
            )
        except FressnapfTrackerInvalidPhoneNumberError:
            errors["base"] = "invalid_phone_number"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug("SMS code request response: %s", response)
            self._context[CONF_USER_ID] = response.id
            self._context[CONF_PHONE_NUMBER] = phone_number
            return errors, True
        return errors, False

    async def _async_verify_sms_code(
        self, sms_code: str
    ) -> tuple[dict[str, str], str | None]:
        """Verify SMS code and return errors and access_token."""
        errors: dict[str, str] = {}
        try:
            verification_response = await self.auth_client.verify_phone_number(
                user_id=self._context[CONF_USER_ID],
                sms_code=sms_code,
            )
        except FressnapfTrackerInvalidTokenError:
            errors["base"] = "invalid_sms_code"
        except Exception:
            _LOGGER.exception("Unexpected exception during SMS code verification")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug(
                "Phone number verification response: %s", verification_response
            )
            return errors, verification_response.user_token.access_token
        return errors, None

    async def _async_request_magic_link(
        self,
        user_input: dict[str, Any] | None,
        step_id: str,
        entry: ConfigEntry | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Request a magic link for a new or existing config entry."""
        errors = errors or {}
        if user_input is not None:
            if entry is None:
                self._async_abort_entries_match({CONF_EMAIL: user_input[CONF_EMAIL]})

            try:
                response = await self.auth_client.request_magic_link(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
            except FressnapfTrackerAuthenticationError:
                errors["base"] = "invalid_auth"
            except FressnapfTrackerConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception while requesting a magic link")
                errors["base"] = "unknown"
            else:
                if entry is not None and entry.data[CONF_USER_ID] != response.user.id:
                    errors["base"] = "account_change_not_allowed"
                else:
                    self._context[CONF_EMAIL] = user_input[CONF_EMAIL]
                    self._context[CONF_USER_ID] = response.user.id
                    self._context[CONF_ACCESS_TOKEN] = response.user_token.access_token
                    self._context[CONF_CUSTOMER_ID] = response.customer_id
                    if entry is None:
                        await self.async_set_unique_id(str(response.user.id))
                        self._abort_if_unique_id_configured()
                    return await self.async_step_magic_link()

        data_schema = STEP_EMAIL_DATA_SCHEMA
        if entry is not None:
            data_schema = self.add_suggested_values_to_schema(
                data_schema,
                {CONF_EMAIL: entry.data.get(CONF_EMAIL)},
            )
        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose an authentication method."""
        return self.async_show_menu(step_id="user", menu_options=["email", "sms"])

    async def async_step_email(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle email authentication credentials."""
        entry = (
            self._get_reconfigure_entry() if self.source == SOURCE_RECONFIGURE else None
        )
        return await self._async_request_magic_link(user_input, "email", entry)

    async def async_step_sms(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle SMS authentication credentials."""
        if self.source == SOURCE_RECONFIGURE:
            return await self._async_reauth_or_reconfigure_sms(
                user_input, self._get_reconfigure_entry(), "sms"
            )

        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_PHONE_NUMBER: user_input[CONF_PHONE_NUMBER]}
            )
            errors, success = await self._async_request_sms_code(
                user_input[CONF_PHONE_NUMBER]
            )
            if success:
                await self.async_set_unique_id(str(self._context[CONF_USER_ID]))
                self._abort_if_unique_id_configured()
                return await self.async_step_sms_code()

        return self.async_show_form(
            step_id="sms", data_schema=STEP_SMS_DATA_SCHEMA, errors=errors
        )

    async def async_step_magic_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for the user to open the emailed magic link."""
        if self._magic_link_task is None:
            self._magic_link_task = self.hass.async_create_task(
                self._async_wait_for_magic_link()
            )

        if self._magic_link_task.done():
            return self.async_show_progress_done(next_step_id="finish_email")
        return self.async_show_progress(
            step_id="magic_link",
            progress_action="wait_for_magic_link",
            description_placeholders={"email": self._context[CONF_EMAIL]},
            progress_task=self._magic_link_task,
        )

    async def async_step_finish_email(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create or update an entry after email authentication completes."""
        assert self._magic_link_task is not None
        error: str | None
        try:
            await self._magic_link_task
        except TimeoutError:
            error = "magic_link_timeout"
        except FressnapfTrackerAuthenticationError:
            error = "invalid_auth"
        except FressnapfTrackerConnectionError:
            error = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception while completing a magic link")
            error = "unknown"
        else:
            error = None
        finally:
            self._magic_link_task = None

        if error is not None:
            errors = {"base": error}
            if self.source == SOURCE_REAUTH:
                return await self._async_request_magic_link(
                    None, "reauth_confirm", self._get_reauth_entry(), errors
                )
            if self.source == SOURCE_RECONFIGURE:
                return await self._async_request_magic_link(
                    None, "email", self._get_reconfigure_entry(), errors
                )
            return await self._async_request_magic_link(None, "email", errors=errors)

        data = {
            CONF_EMAIL: self._context[CONF_EMAIL],
            CONF_USER_ID: self._context[CONF_USER_ID],
            CONF_ACCESS_TOKEN: self._context[CONF_ACCESS_TOKEN],
        }
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), title=data[CONF_EMAIL], data=data
            )
        return self.async_create_entry(title=data[CONF_EMAIL], data=data)

    async def async_step_sms_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the SMS code step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, access_token = await self._async_verify_sms_code(
                user_input[CONF_SMS_CODE]
            )
            if access_token:
                return self.async_create_entry(
                    title=self._context[CONF_PHONE_NUMBER],
                    data={
                        CONF_PHONE_NUMBER: self._context[CONF_PHONE_NUMBER],
                        CONF_USER_ID: self._context[CONF_USER_ID],
                        CONF_ACCESS_TOKEN: access_token,
                    },
                )

        return self.async_show_form(
            step_id="sms_code",
            data_schema=STEP_SMS_CODE_DATA_SCHEMA,
            errors=errors,
        )

    async def _async_reauth_or_reconfigure_sms(
        self,
        user_input: dict[str, Any] | None,
        entry: ConfigEntry,
        step_id: str,
    ) -> ConfigFlowResult:
        """Request an SMS code for an existing config entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, success = await self._async_request_sms_code(
                user_input[CONF_PHONE_NUMBER]
            )
            if success:
                if entry.data[CONF_USER_ID] != self._context[CONF_USER_ID]:
                    errors["base"] = "account_change_not_allowed"
                elif self.source == SOURCE_REAUTH:
                    return await self.async_step_reauth_sms_code()
                elif self.source == SOURCE_RECONFIGURE:
                    return await self.async_step_reconfigure_sms_code()

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                STEP_SMS_DATA_SCHEMA,
                {CONF_PHONE_NUMBER: entry.data.get(CONF_PHONE_NUMBER)},
            ),
            errors=errors,
        )

    async def _async_confirm_sms_code(
        self,
        user_input: dict[str, Any] | None,
        entry: ConfigEntry,
        step_id: str,
    ) -> ConfigFlowResult:
        """Confirm an SMS code for an existing config entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, access_token = await self._async_verify_sms_code(
                user_input[CONF_SMS_CODE]
            )
            if access_token:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_PHONE_NUMBER: self._context[CONF_PHONE_NUMBER],
                        CONF_ACCESS_TOKEN: access_token,
                    },
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=STEP_SMS_CODE_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation step."""
        entry = self._get_reauth_entry()
        if CONF_EMAIL in entry.data:
            return await self._async_request_magic_link(
                user_input, "reauth_confirm", entry
            )
        return await self._async_reauth_or_reconfigure_sms(
            user_input,
            entry,
            "reauth_confirm",
        )

    async def async_step_reauth_sms_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the SMS code step during reauth."""
        return await self._async_confirm_sms_code(
            user_input,
            self._get_reauth_entry(),
            "reauth_sms_code",
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let SMS users choose a new authentication method."""
        entry = self._get_reconfigure_entry()
        if CONF_EMAIL in entry.data:
            return await self._async_request_magic_link(user_input, "email", entry)
        return self.async_show_menu(
            step_id="reconfigure", menu_options=["email", "sms"]
        )

    async def async_step_reconfigure_sms_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the SMS code step during reconfiguration."""
        return await self._async_confirm_sms_code(
            user_input,
            self._get_reconfigure_entry(),
            "reconfigure_sms_code",
        )
