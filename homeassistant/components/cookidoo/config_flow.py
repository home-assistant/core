"""Config flow for Cookidoo integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from cookidoo_api import (
    DEFAULT_COOKIDOO_CONFIG,
    Cookidoo,
    CookidooActionException,
    CookidooAuthBotDetectionException,
    CookidooAuthException,
    CookidooConfigException,
    CookidooNavigationException,
    CookidooSelectorException,
    CookidooUnavailableException,
    CookidooUnexpectedStateException,
)
from playwright.async_api import Error as PlaywrightError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_EMAIL,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
)
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import BROWSER_RUNNER_CHECK_DEFAULT, BROWSER_RUNNER_TIMEOUT, DOMAIN
from .coordinator import CookidooConfigEntry

_LOGGER = logging.getLogger(__name__)

STEP_RUNNER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT): str,
    }
)
STEP_AUTH_DATA_SCHEMA = vol.Schema(
    {
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
)


class CookidooConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cookidoo."""

    VERSION = 1
    reauth_entry: CookidooConfigEntry
    runner = BROWSER_RUNNER_CHECK_DEFAULT[0]

    # async def __init__(self) -> None:
    #     """Initialize the config flow."""
    #     for runner in BROWSER_RUNNER_CHECK_DEFAULT:
    #         host, port = runner.split(":")
    #         if await self.validate_input({CONF_HOST: host, CONF_PORT: port}):
    #             self.runner_proposition = [host, runner]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user/host step."""
        errors: dict[str, str] = {}
        if user_input is not None and not (
            errors := await self.validate_input(user_input)
        ):
            self.runner = user_input
            return self.async_show_form(
                step_id="auth", data_schema=STEP_AUTH_DATA_SCHEMA, errors=errors
            )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_RUNNER_DATA_SCHEMA,
                suggested_values=user_input or self.runner,
            ),
            errors=errors,
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the auth step."""
        errors: dict[str, str] = {}
        if (
            user_input is not None
            and user_input.get(CONF_EMAIL) is not None
            and not (errors := await self.validate_input(user_input))
        ):
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_EMAIL], data={**self.runner, **user_input}
            )
        return self.async_show_form(
            step_id="auth", data_schema=STEP_AUTH_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not (errors := await self.validate_input(user_input)):
                return self.async_update_reload_and_abort(
                    self.reauth_entry, data=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_AUTH_DATA_SCHEMA,
                suggested_values={CONF_EMAIL: self.reauth_entry.data[CONF_EMAIL]},
            ),
            description_placeholders={CONF_NAME: self.reauth_entry.title},
            errors=errors,
        )

    async def validate_input(self, user_input: Mapping[str, Any]) -> dict[str, str]:
        """Input Helper."""

        errors: dict[str, str] = {}
        cookidoo = Cookidoo(
            {
                **DEFAULT_COOKIDOO_CONFIG,
                "browser": "chromium",
                "headless": True,
                "remote_addr": user_input.get(CONF_HOST, self.runner[CONF_HOST]),
                "remote_port": user_input.get(CONF_PORT, self.runner[CONF_PORT]),
                "network_timeout": BROWSER_RUNNER_TIMEOUT,
                "timeout": BROWSER_RUNNER_TIMEOUT,
                "load_media": False,
                "email": user_input.get(CONF_EMAIL, ""),
                "password": user_input.get(CONF_PASSWORD, ""),
                "tracing": False,
                "screenshots": False,
            }
        )
        if not user_input.get(CONF_EMAIL):
            try:
                await cookidoo.validate_cookies()
            except CookidooConfigException:
                errors["base"] = "invalid_host"
            except (
                CookidooUnavailableException,
                CookidooNavigationException,
                CookidooSelectorException,
                CookidooActionException,
                CookidooUnexpectedStateException,
            ):
                errors["base"] = "unknown"
            except (CookidooAuthException, CookidooAuthBotDetectionException):
                # Ok as it reached login page, but as we have not yet any credentials at the moment, it is expected to fails authentication
                pass
            except PlaywrightError:
                errors["base"] = "invalid_host"
        else:
            try:
                await cookidoo.login()
            except CookidooConfigException:
                errors["base"] = "cannot_connect"
            except (
                CookidooUnavailableException,
                CookidooNavigationException,
                CookidooSelectorException,
                CookidooActionException,
                CookidooUnexpectedStateException,
            ):
                errors["base"] = "unknown"
            except CookidooAuthBotDetectionException:
                errors["base"] = "captcha"
            except CookidooAuthException:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(f"{DOMAIN}_{user_input[CONF_EMAIL]}")
        return errors
