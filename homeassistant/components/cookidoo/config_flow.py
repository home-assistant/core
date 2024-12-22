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
    get_country_options,
    get_localization_options,
)
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_COUNTRY, CONF_EMAIL, CONF_LANGUAGE, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    CountrySelector,
    CountrySelectorConfig,
    LanguageSelector,
    LanguageSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

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

    COUNTRY_DATA_SCHEMA: dict
    LANGUAGE_DATA_SCHEMA: dict

    user_input: dict[str, Any]

    async def async_step_reconfigure(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Perform reconfigure upon an user action."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the user step as well as serve for reconfiguration."""
        errors: dict[str, str] = {}

        if user_input is not None and not (
            errors := await self.validate_input(user_input)
        ):
            if self.source == SOURCE_USER:
                self._async_abort_entries_match({CONF_EMAIL: user_input[CONF_EMAIL]})
            self.user_input = user_input
            return await self.async_step_language()
        await self.generate_country_schema()
        suggested_values: dict = {}
        if self.source == SOURCE_RECONFIGURE:
            reconfigure_entry = self._get_reconfigure_entry()
            suggested_values = {
                **suggested_values,
                **reconfigure_entry.data,
            }
        if user_input is not None:
            suggested_values = {**suggested_values, **user_input}
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=vol.Schema(
                    {**AUTH_DATA_SCHEMA, **self.COUNTRY_DATA_SCHEMA}
                ),
                suggested_values=suggested_values,
            ),
            description_placeholders={"cookidoo": "Cookidoo"},
            errors=errors,
        )

    async def async_step_language(
        self,
        language_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Async language step to set up the connection."""
        errors: dict[str, str] = {}
        if language_input is not None and not (
            errors := await self.validate_input(self.user_input, language_input)
        ):
            if self.source == SOURCE_USER:
                return self.async_create_entry(
                    title="Cookidoo", data={**self.user_input, **language_input}
                )
            reconfigure_entry = self._get_reconfigure_entry()
            return self.async_update_reload_and_abort(
                reconfigure_entry,
                data={
                    **reconfigure_entry.data,
                    **self.user_input,
                    **language_input,
                },
            )

        await self.generate_language_schema()
        return self.async_show_form(
            step_id="language",
            data_schema=vol.Schema(self.LANGUAGE_DATA_SCHEMA),
            description_placeholders={"cookidoo": "Cookidoo"},
            errors=errors,
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

        if user_input is not None:
            if not (
                errors := await self.validate_input({**reauth_entry.data, **user_input})
            ):
                if user_input[CONF_EMAIL] != reauth_entry.data[CONF_EMAIL]:
                    self._async_abort_entries_match(
                        {CONF_EMAIL: user_input[CONF_EMAIL]}
                    )
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=vol.Schema(AUTH_DATA_SCHEMA),
                suggested_values={CONF_EMAIL: reauth_entry.data[CONF_EMAIL]},
            ),
            description_placeholders={"cookidoo": "Cookidoo"},
            errors=errors,
        )

    async def generate_country_schema(self) -> None:
        """Generate country schema."""
        self.COUNTRY_DATA_SCHEMA = {
            vol.Required(CONF_COUNTRY): CountrySelector(
                CountrySelectorConfig(
                    countries=[
                        country.upper() for country in await get_country_options()
                    ],
                )
            )
        }

    async def generate_language_schema(self) -> None:
        """Generate language schema."""
        self.LANGUAGE_DATA_SCHEMA = {
            vol.Required(CONF_LANGUAGE): LanguageSelector(
                LanguageSelectorConfig(
                    languages=[
                        option.language
                        for option in await get_localization_options(
                            country=self.user_input[CONF_COUNTRY].lower()
                        )
                    ],
                    native_name=True,
                ),
            ),
        }

    async def validate_input(
        self,
        user_input: dict[str, Any],
        language_input: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Input Helper."""

        errors: dict[str, str] = {}

        data_input: dict[str, Any] = {}

        if self.source == SOURCE_RECONFIGURE:
            reconfigure_entry = self._get_reconfigure_entry()
            data_input = {**data_input, **reconfigure_entry.data}
        data_input = {**data_input, **user_input}
        if language_input:
            data_input = {**data_input, **language_input}
        else:
            data_input[CONF_LANGUAGE] = (
                await get_localization_options(country=data_input[CONF_COUNTRY].lower())
            )[0]  # Pick any language to test login

        session = async_get_clientsession(self.hass)
        cookidoo = Cookidoo(
            session,
            CookidooConfig(
                email=data_input[CONF_EMAIL],
                password=data_input[CONF_PASSWORD],
                localization=CookidooLocalizationConfig(
                    country_code=data_input[CONF_COUNTRY].lower(),
                    language=data_input[CONF_LANGUAGE],
                ),
            ),
        )
        try:
            await cookidoo.login()
            if language_input:
                await cookidoo.get_additional_items()
        except CookidooRequestException:
            errors["base"] = "cannot_connect"
        except CookidooAuthException:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return errors
