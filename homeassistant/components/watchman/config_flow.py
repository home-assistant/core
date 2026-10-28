"""Config flow for Kingspan Watchman SENSiT."""

from collections.abc import Mapping
import logging
from typing import Any, override

from connectsensor.client import AsyncSensorClient
from connectsensor.exceptions import KingspanAPIError, KingspanErrorCode
import probatio

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    API_TIMEOUT,
    CONF_OIL_ENERGY_DENSITY,
    CONF_USAGE_WINDOW,
    DEFAULT_OIL_ENERGY_DENSITY,
    DEFAULT_USAGE_WINDOW,
    DOMAIN,
)
from .coordinator import SENSiTConfigEntry

_LOGGER: logging.Logger = logging.getLogger(__package__)


class SENSiTFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Kingspan Watchman SENSiT."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._errors: dict[str, str] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username.casefold())
            self._abort_if_unique_id_configured()

            error = await self._test_credentials(username, password)
            if error is None:
                return self.async_create_entry(title=username, data=user_input)

            self._errors["base"] = error

        return await self._show_config_form(step_id="user", defaults=user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        self._errors = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username.casefold())
            self._abort_if_unique_id_mismatch()

            error = await self._test_credentials(username, password)
            if error is None:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=username,
                    data_updates={
                        **reconfigure_entry.data,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

            self._errors["base"] = error

        defaults = {
            CONF_USERNAME: reconfigure_entry.data.get(CONF_USERNAME, ""),
            CONF_PASSWORD: reconfigure_entry.data.get(CONF_PASSWORD, ""),
        }
        return await self._show_config_form(
            step_id="reconfigure",
            defaults=user_input or defaults,
        )

    async def async_step_reauth(
        self, _entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm and handle the re-authentication flow."""
        self._errors = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            error = await self._test_credentials(username, password)
            if error is None:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        **reauth_entry.data,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )
            self._errors["base"] = error

        defaults = {
            CONF_USERNAME: reauth_entry.data.get(CONF_USERNAME, ""),
            CONF_PASSWORD: "",
        }
        return await self._show_config_form(
            step_id="reauth_confirm",
            defaults=user_input or defaults,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        _config_entry: SENSiTConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def _show_config_form(
        self,
        step_id: str = "user",
        defaults: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show the configuration form."""
        defaults = defaults or {}
        return self.async_show_form(
            step_id=step_id,
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")
                    ): str,
                    probatio.Required(
                        CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")
                    ): str,
                }
            ),
            errors=self._errors,
        )

    async def _test_credentials(self, username: str, password: str) -> str | None:
        """Return None if credentials are valid, or an error key string."""
        try:
            httpx_client = get_async_client(self.hass)
            async with AsyncSensorClient(
                client=httpx_client, timeout=API_TIMEOUT
            ) as client:
                await client.login(username, password)
        except KingspanAPIError as err:
            return str(err.code.value)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception testing credentials")
            return str(KingspanErrorCode.UNKNOWN.value)
        return None

    @override
    def is_matching(self, other_flow: object) -> bool:
        """Return whether this flow matches another flow."""
        return False


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Initialize the options flow."""
        if user_input is not None:
            _LOGGER.debug(
                "Config options: %s",
                ", ".join([f"{k}='{v}'" for k, v in user_input.items()]),
            )
            return self.async_create_entry(title="", data=user_input)

        options = {
            probatio.Optional(
                CONF_USAGE_WINDOW,
                default=self.config_entry.options.get(
                    CONF_USAGE_WINDOW, DEFAULT_USAGE_WINDOW
                ),
            ): cv.positive_int,
            probatio.Optional(
                CONF_OIL_ENERGY_DENSITY,
                default=self.config_entry.options.get(
                    CONF_OIL_ENERGY_DENSITY, DEFAULT_OIL_ENERGY_DENSITY
                ),
            ): cv.positive_float,
        }

        return self.async_show_form(
            step_id="init", data_schema=probatio.Schema(options)
        )
