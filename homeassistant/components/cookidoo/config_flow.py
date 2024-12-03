"""Config flow for Cookidoo integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from cookidoo_api import (
    Cookidoo,
    CookidooAuthException,
    CookidooConfig,
    CookidooLocalizationConfig,
    CookidooRequestException,
    get_localization_options,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_LOCALIZATION, DOMAIN, LOCALIZATION_SPLIT_CHAR
from .helpers import cookidoo_localization_for_key

_LOGGER = logging.getLogger(__name__)

AUTH_DATA_SCHEMA = {
    vol.Required(CONF_EMAIL): TextSelector(
        TextSelectorConfig(
            type=TextSelectorType.EMAIL,
            autocomplete="email",
        ),
    ),
    vol.Required(CONF_PASSWORD): TextSelector(
        TextSelectorConfig(
            type=TextSelectorType.PASSWORD,
            autocomplete="current-password",
        ),
    ),
}


class CookidooConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cookidoo."""

    LOCALIZATION_DATA_SCHEMA: dict
    localizations: list[CookidooLocalizationConfig] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if (
            user_input is not None
            and not (errors := await self.validate_input(user_input))
            and self.LOCALIZATION_DATA_SCHEMA is not None
        ):
            self._async_abort_entries_match({CONF_EMAIL: user_input[CONF_EMAIL]})
            return self.async_create_entry(title="Cookidoo", data=user_input)
        await self.generate_schemas()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=vol.Schema(
                    {**AUTH_DATA_SCHEMA, **self.LOCALIZATION_DATA_SCHEMA}
                ),
                suggested_values=user_input,
            ),
            errors=errors,
        )

    async def generate_schemas(self) -> None:
        """Generate schemas."""
        self.localizations = await get_localization_options()

        self.LOCALIZATION_DATA_SCHEMA = {
            vol.Required(CONF_LOCALIZATION): SelectSelector(
                SelectSelectorConfig(
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="localization",
                    options=[
                        LOCALIZATION_SPLIT_CHAR.join(
                            [localization.country_code, localization.language]
                        ).lower()
                        for localization in self.localizations
                    ],
                    sort=True,
                ),
            ),
        }

    async def validate_input(self, user_input: Mapping[str, Any]) -> dict[str, str]:
        """Input Helper."""

        errors: dict[str, str] = {}

        session = async_get_clientsession(self.hass)
        cookidoo = Cookidoo(
            session,
            CookidooConfig(
                email=user_input[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
                localization=cookidoo_localization_for_key(
                    self.localizations, user_input[CONF_LOCALIZATION]
                ),
            ),
        )
        try:
            await cookidoo.login()
        except CookidooRequestException:
            errors["base"] = "cannot_connect"
        except CookidooAuthException:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return errors
