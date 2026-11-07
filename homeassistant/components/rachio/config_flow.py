"""Config flow for Rachio integration."""

from collections.abc import Mapping
from http import HTTPStatus
import logging
from typing import Any, override

import probatio
from rachiopy import Rachio
from requests.exceptions import ConnectTimeout

from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from homeassistant.helpers.service_info.zeroconf import (
    ATTR_PROPERTIES_ID,
    ZeroconfServiceInfo,
)

from .const import (
    CONF_MANUAL_RUN_MINS,
    CONF_POLL_ENABLED,
    CONF_POLL_INTERVAL,
    CONF_POLLING,
    DEFAULT_API_DAILY_CALL_LIMIT,
    DEFAULT_MANUAL_RUN_MINS,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    KEY_ID,
    KEY_STATUS,
    KEY_USERNAME,
    MAX_POLL_INTERVAL,
    POLL_INTERVAL_STEP,
)
from .coordinator import (
    controller_calls_per_day,
    hose_timer_calls_per_day,
    min_poll_interval,
)
from .device import RachioConfigEntry

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = probatio.Schema(
    {probatio.Required(probatio.Secret(CONF_API_KEY)): str}, extra=probatio.ALLOW_EXTRA
)
REAUTH_SCHEMA = probatio.Schema({probatio.Required(probatio.Secret(CONF_API_KEY)): str})


async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    rachio = Rachio(data[CONF_API_KEY])
    username = None
    try:
        data = await hass.async_add_executor_job(rachio.person.info)
        _LOGGER.debug("rachio.person.getInfo: %s", data)
        if int(data[0][KEY_STATUS]) != HTTPStatus.OK:
            raise InvalidAuth

        rachio_id = data[1][KEY_ID]
        data = await hass.async_add_executor_job(rachio.person.get, rachio_id)
        _LOGGER.debug("rachio.person.get: %s", data)
        if int(data[0][KEY_STATUS]) != HTTPStatus.OK:
            raise CannotConnect

        username = data[1][KEY_USERNAME]
    except ConnectTimeout as error:
        _LOGGER.error("Could not reach the Rachio API: %s", error)
        raise CannotConnect from error

    # Return info that you want to store in the config entry.
    return {"title": username}


class RachioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rachio."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_API_KEY])
            self._abort_if_unique_id_configured()
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "api_key_url": "https://app.rach.io/",
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new API key."""
        errors = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                reauth_entry = self._get_reauth_entry()
                existing_entry = (
                    self.hass.config_entries.async_entry_for_domain_unique_id(
                        DOMAIN, user_input[CONF_API_KEY]
                    )
                )
                if existing_entry and existing_entry.entry_id != reauth_entry.entry_id:
                    return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    unique_id=user_input[CONF_API_KEY],
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={
                "api_key_url": "https://app.rach.io/",
            },
        )

    @override
    async def async_step_homekit(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle HomeKit discovery."""
        self._async_abort_entries_match()
        await self.async_set_unique_id(discovery_info.properties[ATTR_PROPERTIES_ID])
        self._abort_if_unique_id_configured()
        return await self.async_step_user()

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: RachioConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle a option flow for Rachio."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        if self.config_entry.state is ConfigEntryState.LOADED:
            person = self.config_entry.runtime_data
            controller_count = len(person.controllers)
            base_count = len(person.base_stations)
            rate_limit = person.rate_limit
        else:
            # Setup failed, which must not lock the user out of these options
            controller_count, base_count = 1, 0
            rate_limit = DEFAULT_API_DAILY_CALL_LIMIT

        options = self.config_entry.options
        polling = options.get(CONF_POLLING, {})
        min_interval = min_poll_interval(controller_count, base_count, rate_limit)
        interval = max(
            polling.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL), min_interval
        )

        schema: dict[Any, Any] = {
            probatio.Optional(
                CONF_MANUAL_RUN_MINS,
                default=options.get(CONF_MANUAL_RUN_MINS, DEFAULT_MANUAL_RUN_MINS),
            ): int
        }
        if controller_count:
            schema[probatio.Required(CONF_POLLING)] = section(
                probatio.Schema(
                    {
                        probatio.Optional(
                            CONF_POLL_ENABLED,
                            default=polling.get(CONF_POLL_ENABLED, False),
                        ): bool,
                        probatio.Optional(
                            CONF_POLL_INTERVAL, default=interval
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=min_interval,
                                max=MAX_POLL_INTERVAL,
                                step=POLL_INTERVAL_STEP,
                                mode=NumberSelectorMode.SLIDER,
                                unit_of_measurement=UnitOfTime.MINUTES,
                            )
                        ),
                    }
                ),
                {"collapsed": False},
            )

        controller_calls = controller_calls_per_day(controller_count, interval)
        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(schema),
            description_placeholders={
                "interval": f"{interval:g}",
                "controller_calls": f"{controller_calls:,}",
                "total_calls": f"{controller_calls + hose_timer_calls_per_day(base_count):,}",
                "daily_limit": f"{rate_limit:,}",
                "min_interval": f"{min_interval:g}",
                "controller_count": str(controller_count),
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
