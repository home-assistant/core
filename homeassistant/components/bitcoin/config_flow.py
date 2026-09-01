"""Config flow for the Bitcoin integration."""

from typing import Any, override

from blockchain import exchangerates
from blockchain.exceptions import APIException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CURRENCY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_CURRENCY, DOMAIN, INTEGRATION_TITLE

API_ERRORS = (APIException, OSError, ValueError)


def _get_currencies() -> list[str]:
    """Return the currency codes blockchain.com quotes Bitcoin in."""
    return sorted(exchangerates.get_ticker())


async def _async_get_currencies(hass: HomeAssistant) -> list[str] | None:
    """Return the currencies blockchain.com quotes, or None if it is unreachable."""
    try:
        return await hass.async_add_executor_job(_get_currencies)
    except API_ERRORS:
        return None


def _currency_schema(currencies: list[str]) -> vol.Schema:
    """Build a schema offering the currencies blockchain.com quotes."""
    return vol.Schema(
        {
            vol.Required(CONF_CURRENCY, default=DEFAULT_CURRENCY): SelectSelector(
                SelectSelectorConfig(
                    options=currencies, mode=SelectSelectorMode.DROPDOWN
                )
            )
        }
    )


class BitcoinConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bitcoin."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if (currencies := await _async_get_currencies(self.hass)) is None:
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            return self.async_create_entry(title=INTEGRATION_TITLE, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=_currency_schema(currencies)
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a change of currency."""
        if (currencies := await _async_get_currencies(self.hass)) is None:
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data_updates=user_input
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _currency_schema(currencies), self._get_reconfigure_entry().data
            ),
        )

    async def async_step_import(self, import_data: ConfigType) -> ConfigFlowResult:
        """Handle the import of a YAML sensor platform configuration."""
        if (currencies := await _async_get_currencies(self.hass)) is None:
            return self.async_abort(reason="cannot_connect")

        currency = import_data[CONF_CURRENCY].upper()
        if currency not in currencies:
            return self.async_abort(reason="unknown_currency")

        return self.async_create_entry(
            title=INTEGRATION_TITLE, data={CONF_CURRENCY: currency}
        )
