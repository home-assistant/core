"""Config flow for the AnyList integration."""

from dataclasses import dataclass
import logging
from typing import Any, override
import uuid

from aioanylist import AnyListClient, AnyListError, AuthenticationError, AuthTokens
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_REFRESH_TOKEN, CONF_USER_LOCALE, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="email")
        ),
        probatio.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)


@dataclass(frozen=True, slots=True)
class AnyListAuthData:
    """Validated AnyList authentication data."""

    tokens: AuthTokens
    client_id: str


async def validate_input(
    hass: HomeAssistant,
    user_input: dict[str, str],
    *,
    client_id: str | None = None,
) -> AnyListAuthData:
    """Validate AnyList credentials."""
    client_id = client_id or uuid.uuid4().hex
    client = AnyListClient(
        async_get_clientsession(hass),
        user_email=user_input[CONF_EMAIL],
        client_id=client_id,
    )
    try:
        tokens = await client.sign_in(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
    finally:
        await client.close()
    return AnyListAuthData(tokens=tokens, client_id=client_id)


class AnyListConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an AnyList config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                auth = await validate_input(self.hass, user_input)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except AnyListError, TimeoutError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unexpected exception while authenticating with AnyList"
                )
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(auth.tokens.user_id)
                self._abort_if_unique_id_configured()
                data: dict[str, Any] = {
                    CONF_EMAIL: user_input[CONF_EMAIL],
                    CONF_CLIENT_ID: auth.client_id,
                    CONF_ACCESS_TOKEN: auth.tokens.access_token,
                    CONF_REFRESH_TOKEN: auth.tokens.refresh_token,
                }
                if auth.tokens.user_locale:
                    data[CONF_USER_LOCALE] = auth.tokens.user_locale

                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
