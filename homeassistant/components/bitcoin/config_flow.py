"""Config flow for the Bitcoin integration."""

from typing import Any, override

from blockchain import exchangerates
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CURRENCY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.typing import ConfigType

from . import API_ERRORS
from .const import DEFAULT_CURRENCY, DOMAIN, INTEGRATION_TITLE


def _get_currencies() -> list[str]:
    """Return the currency codes blockchain.com quotes Bitcoin in."""
    return sorted(exchangerates.get_ticker())


async def _async_get_currencies(hass: HomeAssistant) -> list[str] | None:
    """Return the currencies blockchain.com quotes, or None if there are none."""
    try:
        currencies = await hass.async_add_executor_job(_get_currencies)
    except API_ERRORS:
        return None

    # An empty ticker would leave nothing to pick from, so treat it as a failure
    # instead of showing an empty dropdown.
    return currencies or None


def _currency_schema(currencies: list[str]) -> probatio.Schema:
    """Build a schema offering the currencies blockchain.com quotes."""
    # The default has to be one of the offered options, and USD is not always
    # quoted. The list is never empty, an empty one is a connection failure.
    default = DEFAULT_CURRENCY if DEFAULT_CURRENCY in currencies else currencies[0]
    return probatio.Schema(
        {
            probatio.Required(CONF_CURRENCY, default=default): SelectSelector(
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
