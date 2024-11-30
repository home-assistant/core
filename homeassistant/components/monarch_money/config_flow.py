"""Config flow for Monarch Money integration."""

from __future__ import annotations

import logging
from typing import Any

from monarchmoney import LoginFailedException, RequireMFAException
from monarchmoney.monarchmoney import SESSION_FILE
from typedmonarchmoney import TypedMonarchMoney
from typedmonarchmoney.models import MonarchSubscription
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_ID, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_MFA_CODE, DOMAIN, LOGGER

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
            ),
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
            ),
        ),
    }
)

STEP_MFA_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MFA_CODE): str,
    }
)


async def validate_login(
    hass: HomeAssistant,
    data: dict[str, Any],
    email: str | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user. Upon success a session will be saved
    """

    if not email:
        email = data[CONF_EMAIL]
    if not password:
        password = data[CONF_PASSWORD]
    monarch_client = TypedMonarchMoney()
    if CONF_MFA_CODE in data:
        mfa_code = data[CONF_MFA_CODE]
        LOGGER.debug("Attempting to authenticate with MFA code")
        try:
            await monarch_client.multi_factor_authenticate(email, password, mfa_code)
        except KeyError as err:
            # A bug in the backing lib that I don't control throws a KeyError if the MFA code is wrong
            LOGGER.debug("Bad MFA Code")
            raise BadMFA from err
    else:
        LOGGER.debug("Attempting to authenticate")
        try:
            await monarch_client.login(
                email=email,
                password=password,
                save_session=False,
                use_saved_session=False,
            )
        except RequireMFAException:
            raise
        except LoginFailedException as err:
            raise InvalidAuth from err

    LOGGER.debug(f"Connection successful - saving session to file {SESSION_FILE}")
    LOGGER.debug("Obtaining subscription id")
    subs: MonarchSubscription = await monarch_client.get_subscription_details()
    assert subs is not None
    subscription_id = subs.id
    return {
        CONF_TOKEN: monarch_client.token,
        CONF_ID: subscription_id,
    }


class MonarchMoneyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Monarch Money."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self.email: str | None = None
        self.password: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_login(
                    self.hass, user_input, email=self.email, password=self.password
                )
            except RequireMFAException:
                self.email = user_input[CONF_EMAIL]
                self.password = user_input[CONF_PASSWORD]

                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_MFA_DATA_SCHEMA,
                    errors={"base": "mfa_required"},
                )
            except BadMFA:
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_MFA_DATA_SCHEMA,
                    errors={"base": "bad_mfa"},
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(info[CONF_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Monarch Money",
                    data={CONF_TOKEN: info[CONF_TOKEN]},
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class BadMFA(HomeAssistantError):
    """Error to indicate the MFA code was bad."""
