"""Config flow for solax integration."""

import asyncio
import logging
from typing import Any, override

from solax import RealTimeAPI, discover
from solax.discovery import DiscoveryError
from solax.inverter import Inverter
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_MODEL, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers import config_validation as cv, selector

from .const import DOMAIN, model_name_for_inverter

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80
DEFAULT_PASSWORD = ""

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    }
)


class SolaxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solax.

    Two step flow:
    1. Get connection data and do a discovery
    2. If multiple inverters are returned from step 1, then show them to the user to choose one. If one is returned, skip this step.
    """

    def __init__(self) -> None:
        """Initialize the flow."""
        super().__init__()
        self._connection_data: dict[str, Any] = {}
        self._discovered_inverters: dict[str, Inverter] = {}

    def _select_model_schema(self) -> vol.Schema:
        """Return the schema listing only the discovered inverters."""
        return vol.Schema(
            {
                vol.Required(CONF_MODEL): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=sorted(self._discovered_inverters),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

    async def _async_finalize(
        self, model: str, inverter: Inverter, *, step_id: str, data_schema: vol.Schema
    ) -> ConfigFlowResult:
        """Fetch the serial number and create the entry, or redisplay on error."""
        errors: dict[str, str] = {}
        try:
            response = await RealTimeAPI(inverter).get_data()
        except ConnectionError, DiscoveryError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(response.serial_number)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=response.serial_number,
                data={**self._connection_data, CONF_MODEL: model},
            )

        return self.async_show_form(
            step_id=step_id, data_schema=data_schema, errors=errors
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Shows the connection form, and do the discovery.

        If discovery resulted in multiple inverters, show the select_model form,
        If only one skip and finalize.
        """
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors: dict[str, str] = {}
        try:
            discovered = await discover(
                user_input[CONF_IP_ADDRESS],
                user_input[CONF_PORT],
                user_input[CONF_PASSWORD],
                return_when=asyncio.ALL_COMPLETED,
            )
            self._discovered_inverters = {
                model_name_for_inverter(inverter): inverter for inverter in discovered
            }
        except ConnectionError, DiscoveryError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self._connection_data = user_input

            if len(self._discovered_inverters) > 1:
                return await self.async_step_select_model()

            model, inverter = next(iter(self._discovered_inverters.items()))
            return await self._async_finalize(
                model, inverter, step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_select_model(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle model selection when multiple inverters matched."""
        if user_input is not None:
            model = user_input[CONF_MODEL]
            return await self._async_finalize(
                model,
                self._discovered_inverters[model],
                step_id="select_model",
                data_schema=self._select_model_schema(),
            )

        return self.async_show_form(
            step_id="select_model", data_schema=self._select_model_schema()
        )
