"""Config flow for the Zonneplan integration."""

import logging
from typing import Any, override

from pyzonneplan import (
    OtpChallenge,
    Zonneplan,
    ZonneplanConnectionError,
    ZonneplanInvalidOtpError,
    ZonneplanTimeoutError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
    }
)
STEP_OTP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("otp"): TextSelector(
            TextSelectorConfig(type=TextSelectorType.NUMBER)
        )
    }
)


class ZonneplanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zonneplan."""

    _client: Zonneplan
    _challenge: OtpChallenge

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: request an OTP for the given email."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._client = Zonneplan(
                email=user_input[CONF_EMAIL],
                session=async_get_clientsession(self.hass),
            )
            try:
                self._challenge = await self._client.async_request_otp(
                    source_name=self.hass.config.location_name
                )
            except ZonneplanConnectionError:
                errors["base"] = "cannot_connect"
            except ZonneplanTimeoutError:
                errors["base"] = "timeout_connect"
            except Exception:
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self.async_step_otp()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle submission of the mailed one-time password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                token = await self._client.async_submit_otp(
                    self._challenge, user_input["otp"]
                )
                account = await self._client.async_get_account()
            except ZonneplanInvalidOtpError:
                errors["base"] = "invalid_auth"
            except ZonneplanConnectionError:
                errors["base"] = "cannot_connect"
            except ZonneplanTimeoutError:
                errors["base"] = "timeout_connect"
            except Exception:
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(account.user_account.uuid)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=account.user_account.full_name,
                    data={
                        CONF_EMAIL: account.user_account.email,
                        CONF_TOKEN: token.as_dict(),
                    },
                )

        return self.async_show_form(
            step_id="otp",
            data_schema=STEP_OTP_DATA_SCHEMA,
            errors=errors,
            description_placeholders={CONF_EMAIL: self._challenge.email},
        )
