"""Config flow for Suez Water integration."""

from __future__ import annotations

import logging
from typing import Any

from pysuez import PySuezError, SuezClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_COUNTER_ID, CONF_REFRESH_INTERVAL, DATA_REFRESH_INTERVAL, DOMAIN
from .coordinator import SuezWaterConfigEntry

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_COUNTER_ID): str,
    }
)

MIN_REFRESH_INTERVAL = 1
MAX_REFRESH_INTERVAL = 23


async def validate_input(data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    try:
        counter_id = data.get(CONF_COUNTER_ID)
        client = SuezClient(
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            counter_id,
        )
        try:
            if not await client.check_credentials():
                raise InvalidAuth
        except PySuezError as ex:
            raise CannotConnect from ex

        if counter_id is None:
            try:
                data[CONF_COUNTER_ID] = await client.find_counter()
            except PySuezError as ex:
                raise CounterNotFound from ex
    finally:
        await client.close_session()


class SuezWaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Suez Water."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()
            try:
                await validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CounterNotFound:
                errors["base"] = "counter_not_found"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"tout_sur_mon_eau": "Tout sur mon Eau"},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguring integration."""
        config_entry: SuezWaterConfigEntry = self._get_reconfigure_entry()

        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(config_entry.data[CONF_USERNAME])
            self._abort_if_unique_id_mismatch()

            user_refresh: int = user_input[CONF_REFRESH_INTERVAL]

            return self.async_update_reload_and_abort(
                config_entry,
                data={
                    **config_entry.data,
                    CONF_REFRESH_INTERVAL: user_refresh,
                },
            )

        return self.async_show_form(
            step_id="reconfigure",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REFRESH_INTERVAL,
                        default=config_entry.data.get(
                            CONF_REFRESH_INTERVAL, DATA_REFRESH_INTERVAL
                        ),
                    ): vol.All(
                        int,
                        vol.Range(min=MIN_REFRESH_INTERVAL, max=MAX_REFRESH_INTERVAL),
                    )
                }
            ),
            description_placeholders={
                "refresh_max": f"{MAX_REFRESH_INTERVAL}",
                "refresh_min": f"{MIN_REFRESH_INTERVAL}",
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CounterNotFound(HomeAssistantError):
    """Error to indicate we cannot automatically found the counter id."""
