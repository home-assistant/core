"""Config flow for kraken integration."""

from __future__ import annotations

from typing import Any

import krakenex
from pykrakenapi.pykrakenapi import KrakenAPI
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import CONF_TRACKED_ASSET_PAIRS, DEFAULT_SCAN_INTERVAL, DOMAIN
from .utils import get_tradable_asset_pairs


class KrakenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for kraken."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> KrakenOptionsFlowHandler:
        """Get the options flow for this handler."""
        return KrakenOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        if user_input is not None:
            return self.async_create_entry(title=DOMAIN, data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=None,
            errors={},
        )


class KrakenOptionsFlowHandler(OptionsFlow):
    """Handle Kraken client options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Kraken options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        api = KrakenAPI(krakenex.API(), retry=0, crl_sleep=0)
        tradable_asset_pairs = await self.hass.async_add_executor_job(
            get_tradable_asset_pairs, api
        )
        tradable_asset_pairs_for_multi_select = {v: v for v in tradable_asset_pairs}

        # Ensure that a previously selected tracked asset pair is still available in multiselect
        # even if it is not tradable anymore
        tracked_asset_pairs = self.config_entry.options.get(
            CONF_TRACKED_ASSET_PAIRS, []
        )
        tradable_asset_pairs_for_multi_select.update(
            {
                tracked_asset_pair: tracked_asset_pair
                for tracked_asset_pair in tracked_asset_pairs
            }
        )

        options = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): int,
            vol.Optional(
                CONF_TRACKED_ASSET_PAIRS,
                default=tracked_asset_pairs,
            ): cv.multi_select(tradable_asset_pairs_for_multi_select),
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
