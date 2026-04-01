"""Config flow for the BIR integration."""

from __future__ import annotations

import logging
from typing import Any

from pybirno import BirClient, BirError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_ADDRESS, CONF_PROPERTY_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_SEARCH_LENGTH = 3


class BirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BIR."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._addresses: list[dict[str, Any]] = []
        self._search_query: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            search_query = user_input.get("address_search", "").strip()

            if len(search_query) < MIN_SEARCH_LENGTH:
                errors["base"] = "search_too_short"
            else:
                try:
                    session = async_get_clientsession(self.hass)
                    addresses = await BirClient.search_addresses(session, search_query)
                    self._addresses = [
                        {"id": addr.property_id, "adresse": addr.address}
                        for addr in addresses
                    ]
                    self._search_query = search_query

                    if not self._addresses:
                        errors["base"] = "no_addresses_found"
                    else:
                        return await self.async_step_select_address()

                except BirError:
                    _LOGGER.exception("Error searching for addresses")
                    errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("address_search"): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.TEXT,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_select_address(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle address selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_id = user_input.get("selected_address")

            if selected_id:
                selected = next(
                    (a for a in self._addresses if a["id"] == selected_id), None
                )
                if selected:
                    try:
                        session = async_get_clientsession(self.hass)
                        client = BirClient(selected["id"], session)
                        await client.authenticate()

                        await self.async_set_unique_id(f"bir_{selected['id']}")
                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=selected["adresse"],
                            data={
                                CONF_PROPERTY_ID: selected["id"],
                                CONF_ADDRESS: selected["adresse"],
                            },
                        )
                    except AbortFlow:
                        raise
                    except BirError:
                        _LOGGER.exception("Error validating property")
                        errors["base"] = "cannot_connect"

        options = [
            SelectOptionDict(
                value=addr["id"],
                label=addr["adresse"],
            )
            for addr in self._addresses
        ]

        return self.async_show_form(
            step_id="select_address",
            data_schema=vol.Schema(
                {
                    vol.Required("selected_address"): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "count": str(len(self._addresses)),
                "query": self._search_query,
            },
        )
