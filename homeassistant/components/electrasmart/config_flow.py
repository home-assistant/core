"""Config flow for Electra Air Conditioner integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from electrasmart.api import STATUS_SUCCESS, Attributes, ElectraAPI, ElectraApiError
from electrasmart.api.utils import generate_imei
import probatio

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_IMEI, CONF_OTP, CONF_PHONE_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ElectraSmartConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Electra Air Conditioner."""

    VERSION = 1

    def __init__(self) -> None:
        """Device settings."""
        self._phone_number: str | None = None
        self._description_placeholders = None
        self._otp: str | None = None
        self._imei: str | None = None
        self._token: str | None = None
        self._api: ElectraAPI | None = None
        self._reauth_entry: ConfigEntry | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        if not self._api:
            self._api = ElectraAPI(async_get_clientsession(self.hass))

        errors: dict[str, Any] = {}

        if user_input is None:
            return self._show_setup_form(user_input, errors, "user")

        return await self._validate_phone_number(user_input)

    def _show_setup_form(
        self,
        user_input: dict[str, str] | None = None,
        errors: dict[str, str] | None = None,
        step_id: str = "user",
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""
        if user_input is None:
            user_input = {}

        if step_id == "user":
            schema = {
                probatio.Required(
                    CONF_PHONE_NUMBER, default=user_input.get(CONF_PHONE_NUMBER, "")
                ): str
            }
        else:
            schema = {
                probatio.Required(CONF_OTP, default=user_input.get(CONF_OTP, "")): str
            }

        return self.async_show_form(
            step_id=step_id,
            data_schema=probatio.Schema(schema),
            errors=errors or {},
            description_placeholders=self._description_placeholders,
        )

    async def _validate_phone_number(
        self, user_input: dict[str, str]
    ) -> ConfigFlowResult:
        """Check if config is valid and create entry if so."""

        self._phone_number = user_input[CONF_PHONE_NUMBER]
        self._imei = generate_imei()

        # Check if already configured
        if self.unique_id is None:
            await self.async_set_unique_id(self._phone_number)
            self._abort_if_unique_id_configured()

        assert isinstance(self._api, ElectraAPI)

        try:
            resp = await self._api.generate_new_token(self._phone_number, self._imei)
        except ElectraApiError as exp:
            _LOGGER.error("Failed to connect to API: %s", exp)
            return self._show_setup_form(user_input, {"base": "cannot_connect"}, "user")

        if resp[Attributes.STATUS] == STATUS_SUCCESS:
            if resp[Attributes.DATA][Attributes.RES] != STATUS_SUCCESS:
                return self._show_setup_form(
                    user_input, {CONF_PHONE_NUMBER: "invalid_phone_number"}, "user"
                )

        return await self.async_step_one_time_password()

    async def _validate_one_time_password(
        self, user_input: dict[str, str], step_id: str = CONF_OTP
    ) -> ConfigFlowResult:
        self._otp = user_input[CONF_OTP]

        assert isinstance(self._api, ElectraAPI)
        assert isinstance(self._imei, str)
        assert isinstance(self._phone_number, str)
        assert isinstance(self._otp, str)

        try:
            resp = await self._api.validate_one_time_password(
                self._otp, self._imei, self._phone_number
            )
        except ElectraApiError as exp:
            _LOGGER.error("Failed to connect to API: %s", exp)
            return self._show_setup_form(
                user_input, {"base": "cannot_connect"}, step_id
            )

        if resp[Attributes.DATA][Attributes.RES] == STATUS_SUCCESS:
            self._token = resp[Attributes.DATA][Attributes.TOKEN]

            data = {
                CONF_TOKEN: self._token,
                CONF_IMEI: self._imei,
                CONF_PHONE_NUMBER: self._phone_number,
            }
            if self._reauth_entry is not None:
                return self.async_update_reload_and_abort(self._reauth_entry, data=data)
            return self.async_create_entry(title=self._phone_number, data=data)
        return self._show_setup_form(user_input, {CONF_OTP: "invalid_auth"}, step_id)

    async def async_step_one_time_password(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Ask the verification code to the user."""
        if errors is None:
            errors = {}

        if user_input is None:
            return await self._show_otp_form(errors)

        return await self._validate_one_time_password(user_input)

    async def _show_otp_form(
        self,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the verification_code form to the user."""

        return self.async_show_form(
            step_id=CONF_OTP,
            data_schema=probatio.Schema({probatio.Required(CONF_OTP): str}),
            errors=errors or {},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle the reauthentication of a locked out account."""
        self._reauth_entry = self._get_reauth_entry()
        self._phone_number = self._reauth_entry.data[CONF_PHONE_NUMBER]
        self._imei = generate_imei()

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new one-time password to clear the lockout."""
        if self._api is None:
            self._api = ElectraAPI(async_get_clientsession(self.hass))

        if user_input is None:
            # Only a confirmation, so that opening the dialog does not send a code.
            return self.async_show_form(step_id="reauth_confirm")

        errors: dict[str, str] = {}
        assert isinstance(self._api, ElectraAPI)
        assert self._phone_number is not None
        assert self._imei is not None

        # A new one-time password has to be requested before it can be entered.
        try:
            resp = await self._api.generate_new_token(self._phone_number, self._imei)
        except ElectraApiError as exp:
            _LOGGER.error("Failed to connect to API: %s", exp)
            errors = {"base": "cannot_connect"}
        else:
            if (
                resp[Attributes.STATUS] == STATUS_SUCCESS
                and resp[Attributes.DATA][Attributes.RES] != STATUS_SUCCESS
            ):
                errors = {"base": "invalid_phone_number"}

        if errors:
            # Keep the confirmation, so the request can be retried.
            return self.async_show_form(step_id="reauth_confirm", errors=errors)

        return await self.async_step_one_time_password()
