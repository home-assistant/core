"""Config flow for solarlog integration."""

from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import ParseResult, urlparse

from solarlog_cli.solarlog_connector import SolarLogConnector
from solarlog_cli.solarlog_exceptions import (
    SolarLogAuthenticationError,
    SolarLogConnectionError,
    SolarLogError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.util import slugify

from .const import CONF_HAS_PWD, DEFAULT_HOST, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SolarLogConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for solarlog."""

    VERSION = 1
    MINOR_VERSION = 3

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict = {}
        self._user_input: dict = {}

    def _parse_url(self, host: str) -> str:
        """Return parsed host url."""
        url = urlparse(host, "http")
        netloc = url.netloc or url.path
        path = url.path if url.netloc else ""
        url = ParseResult("http", netloc, path, *url[3:])
        return url.geturl()

    async def _test_connection(self, host: str) -> bool:
        """Check if we can connect to the Solar-Log device."""
        solarlog = SolarLogConnector(host)
        try:
            await solarlog.test_connection()
        except SolarLogConnectionError:
            self._errors = {CONF_HOST: "cannot_connect"}
            return False
        except SolarLogError:
            self._errors = {CONF_HOST: "unknown"}
            return False
        finally:
            await solarlog.client.close()

        return True

    async def _test_extended_data(self, host: str, pwd: str = "") -> bool:
        """Check if we get extended data from Solar-Log device."""
        response: bool = False
        solarlog = SolarLogConnector(host, password=pwd)
        try:
            response = await solarlog.test_extended_data_available()
        except SolarLogAuthenticationError:
            self._errors = {CONF_HOST: "password_error"}
            response = False
        except SolarLogError:
            self._errors = {CONF_HOST: "unknown"}
            response = False
        finally:
            await solarlog.client.close()

        return response

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user initializes a integration."""
        self._errors = {}
        if user_input is not None:
            user_input[CONF_HOST] = self._parse_url(user_input[CONF_HOST])

            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            user_input[CONF_NAME] = slugify(user_input[CONF_NAME])

            if await self._test_connection(user_input[CONF_HOST]):
                if user_input[CONF_HAS_PWD]:
                    self._user_input = user_input
                    return await self.async_step_password()

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        else:
            user_input = {CONF_NAME: DEFAULT_NAME, CONF_HOST: DEFAULT_HOST}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    vol.Required(CONF_HAS_PWD, default=False): bool,
                }
            ),
            errors=self._errors,
        )

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user sets password ."""
        self._errors = {}
        if user_input is not None:
            if await self._test_extended_data(
                self._user_input[CONF_HOST], user_input[CONF_PASSWORD]
            ):
                self._user_input |= user_input
                return self.async_create_entry(
                    title=self._user_input[CONF_NAME], data=self._user_input
                )
        else:
            user_input = {CONF_PASSWORD: ""}

        return self.async_show_form(
            step_id="password",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=self._errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        reconfigure_entry = self._get_reconfigure_entry()
        if user_input is not None:
            if not user_input[CONF_HAS_PWD] or user_input.get(CONF_PASSWORD, "") == "":
                user_input[CONF_PASSWORD] = ""
                user_input[CONF_HAS_PWD] = False
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=user_input
                )

            if await self._test_extended_data(
                reconfigure_entry.data[CONF_HOST], user_input.get(CONF_PASSWORD, "")
            ):
                # if password has been provided, only save if extended data is available
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_HAS_PWD, default=reconfigure_entry.data[CONF_HAS_PWD]
                    ): bool,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle flow upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization flow."""
        reauth_entry = self._get_reauth_entry()
        if user_input and await self._test_extended_data(
            reauth_entry.data[CONF_HOST], user_input.get(CONF_PASSWORD, "")
        ):
            return self.async_update_reload_and_abort(
                reauth_entry, data_updates=user_input
            )

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_HAS_PWD, default=reauth_entry.data[CONF_HAS_PWD]
                ): bool,
                vol.Optional(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=data_schema,
            errors=self._errors,
        )
