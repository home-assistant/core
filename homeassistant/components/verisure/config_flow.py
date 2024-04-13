"""Config flow for Verisure integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from verisure import (
    Error as VerisureError,
    LoginError as VerisureLoginError,
    ResponseError as VerisureResponseError,
    Session as Verisure,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_CODE, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_GIID,
    CONF_LOCK_CODE_DIGITS,
    DEFAULT_LOCK_CODE_DIGITS,
    DOMAIN,
    LOGGER,
)


class VerisureConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Verisure."""

    VERSION = 2

    email: str
    entry: ConfigEntry
    password: str
    verisure: Verisure

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> VerisureOptionsFlowHandler:
        """Get the options flow for this handler."""
        return VerisureOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.email = user_input[CONF_EMAIL]
            self.password = user_input[CONF_PASSWORD]
            self.verisure = Verisure(
                username=self.email,
                password=self.password,
                cookie_file_name=self.hass.config.path(
                    STORAGE_DIR, f"verisure_{user_input[CONF_EMAIL]}"
                ),
            )

            try:
                await self.hass.async_add_executor_job(self.verisure.login)
            except VerisureLoginError as ex:
                if "Multifactor authentication enabled" in str(ex):
                    try:
                        await self.hass.async_add_executor_job(
                            self.verisure.request_mfa
                        )
                    except (
                        VerisureLoginError,
                        VerisureError,
                        VerisureResponseError,
                    ) as mfa_ex:
                        LOGGER.debug(
                            "Unexpected response from Verisure during MFA set up, %s",
                            mfa_ex,
                        )
                        errors["base"] = "unknown_mfa"
                    else:
                        return await self.async_step_mfa()
                else:
                    LOGGER.debug("Could not log in to Verisure, %s", ex)
                    errors["base"] = "invalid_auth"
            except (VerisureError, VerisureResponseError) as ex:
                LOGGER.debug("Unexpected response from Verisure, %s", ex)
                errors["base"] = "unknown"
            else:
                return await self.async_step_installation()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle multifactor authentication step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    self.verisure.validate_mfa, user_input[CONF_CODE]
                )
            except VerisureLoginError as ex:
                LOGGER.debug("Could not log in to Verisure, %s", ex)
                errors["base"] = "invalid_auth"
            except (VerisureError, VerisureResponseError) as ex:
                LOGGER.debug("Unexpected response from Verisure, %s", ex)
                errors["base"] = "unknown"
            else:
                return await self.async_step_installation()

        return self.async_show_form(
            step_id="mfa",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CODE): vol.All(
                        vol.Coerce(str), vol.Length(min=6, max=6)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_installation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select Verisure installation to add."""
        installations_data = await self.hass.async_add_executor_job(
            self.verisure.get_installations
        )
        installations = {
            inst["giid"]: f"{inst['alias']} ({inst['address']['street']})"
            for inst in (
                installations_data.get("data", {})
                .get("account", {})
                .get("installations", [])
            )
        }

        if user_input is None:
            if len(installations) != 1:
                return self.async_show_form(
                    step_id="installation",
                    data_schema=vol.Schema(
                        {vol.Required(CONF_GIID): vol.In(installations)}
                    ),
                )
            user_input = {CONF_GIID: list(installations)[0]}

        await self.async_set_unique_id(user_input[CONF_GIID])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=installations[user_input[CONF_GIID]],
            data={
                CONF_EMAIL: self.email,
                CONF_PASSWORD: self.password,
                CONF_GIID: user_input[CONF_GIID],
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with Verisure."""
        self.entry = cast(
            ConfigEntry,
            self.hass.config_entries.async_get_entry(self.context["entry_id"]),
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with Verisure."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.email = user_input[CONF_EMAIL]
            self.password = user_input[CONF_PASSWORD]

            self.verisure = Verisure(
                username=self.email,
                password=self.password,
                cookie_file_name=self.hass.config.path(
                    STORAGE_DIR, f"verisure_{user_input[CONF_EMAIL]}"
                ),
            )

            try:
                await self.hass.async_add_executor_job(self.verisure.login)
            except VerisureLoginError as ex:
                if "Multifactor authentication enabled" in str(ex):
                    try:
                        await self.hass.async_add_executor_job(
                            self.verisure.request_mfa
                        )
                    except (
                        VerisureLoginError,
                        VerisureError,
                        VerisureResponseError,
                    ) as mfa_ex:
                        LOGGER.debug(
                            "Unexpected response from Verisure during MFA set up, %s",
                            mfa_ex,
                        )
                        errors["base"] = "unknown_mfa"
                    else:
                        return await self.async_step_reauth_mfa()
                else:
                    LOGGER.debug("Could not log in to Verisure, %s", ex)
                    errors["base"] = "invalid_auth"
            except (VerisureError, VerisureResponseError) as ex:
                LOGGER.debug("Unexpected response from Verisure, %s", ex)
                errors["base"] = "unknown"
            else:
                data = self.entry.data.copy()
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={
                        **data,
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL, default=self.entry.data[CONF_EMAIL]): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle multifactor authentication step during re-authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    self.verisure.validate_mfa, user_input[CONF_CODE]
                )
                await self.hass.async_add_executor_job(self.verisure.login)
            except VerisureLoginError as ex:
                LOGGER.debug("Could not log in to Verisure, %s", ex)
                errors["base"] = "invalid_auth"
            except (VerisureError, VerisureResponseError) as ex:
                LOGGER.debug("Unexpected response from Verisure, %s", ex)
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={
                        **self.entry.data,
                        CONF_EMAIL: self.email,
                        CONF_PASSWORD: self.password,
                    },
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_mfa",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CODE): vol.All(
                        vol.Coerce(str),
                        vol.Length(min=6, max=6),
                    )
                }
            ),
            errors=errors,
        )


class VerisureOptionsFlowHandler(OptionsFlow):
    """Handle Verisure options."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize Verisure options flow."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Verisure options."""
        errors: dict[str, Any] = {}

        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LOCK_CODE_DIGITS,
                        description={
                            "suggested_value": self.entry.options.get(
                                CONF_LOCK_CODE_DIGITS, DEFAULT_LOCK_CODE_DIGITS
                            )
                        },
                    ): int,
                }
            ),
            errors=errors,
        )
