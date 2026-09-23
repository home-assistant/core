"""Config flow for the Community store."""

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, override

from aiogithubapi import (
    GitHubDeviceAPI,
    GitHubException,
    GitHubLoginDeviceModel,
    GitHubLoginOauthModel,
)
from aiogithubapi.common.const import OAUTH_USER_LOGIN
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.generated.countries import COUNTRIES
from homeassistant.helpers import aiohttp_client

from .base import StoreConfigEntry
from .const import CLIENT_ID, CLIENT_NAME, COUNTRY_ALL, DOMAIN
from .utils.configuration_schema import APPDAEMON, COUNTRY
from .utils.logger import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class StoreConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the Community store."""

    VERSION = 1

    hass: HomeAssistant
    activation_task: asyncio.Task | None = None
    device: GitHubDeviceAPI | None = None

    _registration: GitHubLoginDeviceModel | None = None
    _activation: GitHubLoginOauthModel | None = None
    _reauth: bool = False

    def __init__(self) -> None:
        """Initialize."""
        self._errors: dict[str, str] = {}
        self._user_input: dict[str, Any] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        self._errors = {}
        if user_input:
            if [x for x in user_input if x.startswith("acc_") and not user_input[x]]:
                self._errors["base"] = "acc"
                return await self._show_config_form(user_input)

            self._user_input = user_input

            return await self.async_step_device(user_input)

        # Initial form
        return await self._show_config_form(user_input)

    async def async_step_device(
        self, _user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Handle device steps."""
        if not self.device:
            self.device = GitHubDeviceAPI(
                client_id=CLIENT_ID,
                session=aiohttp_client.async_get_clientsession(self.hass),
                client_name=CLIENT_NAME,
            )
            try:
                response = await self.device.register()
                self._registration = response.data
            except GitHubException as exception:
                LOGGER.exception(exception)
                return self.async_abort(reason="could_not_register")

        device = self.device
        if (registration := self._registration) is None:
            return self.async_abort(reason="could_not_register")

        async def _wait_for_activation() -> None:
            activation = await device.activation(device_code=registration.device_code)
            self._activation = activation.data

        if self.activation_task is None:
            self.activation_task = self.hass.async_create_task(_wait_for_activation())

        if self.activation_task.done():
            if (task_exception := self.activation_task.exception()) is not None:
                LOGGER.exception(task_exception)
                return self.async_show_progress_done(next_step_id="could_not_register")
            return self.async_show_progress_done(next_step_id="device_done")

        return self.async_show_progress(
            step_id="device",
            progress_action="wait_for_device",
            description_placeholders={
                "url": OAUTH_USER_LOGIN,
                "code": registration.user_code,
            },
            progress_task=self.activation_task,
        )

    async def _show_config_form(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Show the configuration form to edit location data."""

        if not user_input:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "acc_logs", default=user_input.get("acc_logs", False)
                    ): bool,
                    vol.Required(
                        "acc_addons", default=user_input.get("acc_addons", False)
                    ): bool,
                    vol.Required(
                        "acc_untested", default=user_input.get("acc_untested", False)
                    ): bool,
                    vol.Required(
                        "acc_disable", default=user_input.get("acc_disable", False)
                    ): bool,
                }
            ),
            errors=self._errors,
        )

    async def async_step_device_done(
        self, user_input: dict[str, bool] | None = None
    ) -> ConfigFlowResult:
        """Handle device steps."""
        if (activation := self._activation) is None:
            return self.async_abort(reason="could_not_register")

        if self._reauth:
            existing_entry = self._get_reauth_entry()
            self.hass.config_entries.async_update_entry(
                existing_entry,
                data={**existing_entry.data, "token": activation.access_token},
            )
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title="",
            data={
                "token": activation.access_token,
            },
        )

    async def async_step_could_not_register(
        self, _user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle issues that need transition await from progress step."""
        return self.async_abort(reason="could_not_register")

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        self._reauth = True
        return await self.async_step_device(None)

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> StoreOptionsFlow:
        """Create the options flow."""
        return StoreOptionsFlow()


class StoreOptionsFlow(OptionsFlow):
    """Options flow for the Community store."""

    async def async_step_init(
        self, _user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        entries: list[StoreConfigEntry] = self.hass.config_entries.async_loaded_entries(
            DOMAIN
        )
        if not entries:
            return self.async_abort(reason="not_setup")

        store = entries[0].runtime_data
        if store.queue.has_pending_tasks:
            return self.async_abort(reason="pending_tasks")

        schema = {
            vol.Optional(COUNTRY, default=store.configuration.country): vol.In(
                [COUNTRY_ALL, *sorted(COUNTRIES)]
            ),
            vol.Optional(APPDAEMON, default=store.configuration.appdaemon): bool,
        }

        return self.async_show_form(step_id="user", data_schema=vol.Schema(schema))
