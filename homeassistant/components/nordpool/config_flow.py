"""Adds config flow for Nord Pool integration."""

from __future__ import annotations

from typing import Any

from pynordpool import (
    Currency,
    NordPoolClient,
    NordPoolEmptyResponseError,
    NordPoolError,
)
from pynordpool.const import AREAS
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CURRENCY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util

from .const import CONF_AREAS, DEFAULT_NAME, DOMAIN

SELECT_AREAS = [
    SelectOptionDict(value=area, label=name) for area, name in AREAS.items()
]
SELECT_CURRENCY = [currency.value for currency in Currency]

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AREAS, default=[]): SelectSelector(
            SelectSelectorConfig(
                options=SELECT_AREAS,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
                sort=True,
            )
        ),
        vol.Required(CONF_CURRENCY, default="SEK"): SelectSelector(
            SelectSelectorConfig(
                options=SELECT_CURRENCY,
                multiple=False,
                mode=SelectSelectorMode.DROPDOWN,
                sort=True,
            )
        ),
    }
)


async def test_api(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, str]:
    """Test fetch data from Nord Pool."""
    client = NordPoolClient(async_get_clientsession(hass))
    try:
        await client.async_get_delivery_period(
            dt_util.now(),
            Currency(user_input[CONF_CURRENCY]),
            user_input[CONF_AREAS],
        )
    except NordPoolEmptyResponseError:
        return {"base": "no_data"}
    except NordPoolError:
        return {"base": "cannot_connect"}

    return {}


class NordpoolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nord Pool integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input:
            errors = await test_api(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfiguration step."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input:
            errors = await test_api(self.hass, user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, user_input or reconfigure_entry.data
            ),
            errors=errors,
        )
