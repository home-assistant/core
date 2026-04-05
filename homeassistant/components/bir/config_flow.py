"""Config flow for the BIR integration."""

from __future__ import annotations

from typing import Any

from pybirno import Address, BirClient, BirError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
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

from .const import CONF_PROPERTY_ID, DOMAIN

MIN_SEARCH_LENGTH = 3


class BirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BIR."""

    VERSION = 1

    _addresses: list[Address]
    _search_query: str

    async def _async_search_address(
        self, step_id: str, user_input: dict[str, Any] | None, next_step: str
    ) -> ConfigFlowResult:
        """Handle an address search step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            search_query = user_input.get("address_search", "").strip()

            if len(search_query) < MIN_SEARCH_LENGTH:
                errors["base"] = "search_too_short"
            else:
                try:
                    session = async_get_clientsession(self.hass)
                    self._addresses = await BirClient.search_addresses(
                        session, search_query
                    )
                    self._search_query = search_query

                    if not self._addresses:
                        errors["base"] = "no_addresses_found"
                    else:
                        return await getattr(self, f"async_step_{next_step}")()

                except BirError:
                    errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id=step_id,
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self._async_search_address(
            "user", user_input, "select_address"
        )

    async def _async_select_address(
        self,
        step_id: str,
        user_input: dict[str, Any] | None,
        on_success: str,
    ) -> ConfigFlowResult:
        """Handle address selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_id = user_input.get("selected_address")

            if selected_id:
                selected = next(
                    (a for a in self._addresses if a.property_id == selected_id),
                    None,
                )
                if selected:
                    try:
                        session = async_get_clientsession(self.hass)
                        client = BirClient(selected.property_id, session)
                        await client.authenticate()
                    except BirError:
                        errors["base"] = "cannot_connect"
                    else:
                        await self.async_set_unique_id(f"bir_{selected.property_id}")

                        if on_success == "create":
                            self._abort_if_unique_id_configured()
                            return self.async_create_entry(
                                title=selected.address,
                                data={
                                    CONF_PROPERTY_ID: selected.property_id,
                                    CONF_ADDRESS: selected.address,
                                },
                            )

                        # reconfigure
                        self._abort_if_unique_id_configured(
                            updates={
                                CONF_PROPERTY_ID: selected.property_id,
                                CONF_ADDRESS: selected.address,
                            },
                        )
                        return self.async_update_reload_and_abort(
                            self._get_reconfigure_entry(),
                            unique_id=f"bir_{selected.property_id}",
                            title=selected.address,
                            data={
                                CONF_PROPERTY_ID: selected.property_id,
                                CONF_ADDRESS: selected.address,
                            },
                        )

        options = [
            SelectOptionDict(
                value=addr.property_id,
                label=addr.address,
            )
            for addr in self._addresses
        ]

        return self.async_show_form(
            step_id=step_id,
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

    async def async_step_select_address(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle address selection step."""
        return await self._async_select_address(
            "select_address", user_input, "create"
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration flow."""
        return await self._async_search_address(
            "reconfigure", user_input, "reconfigure_select_address"
        )

    async def async_step_reconfigure_select_address(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle address selection during reconfiguration."""
        return await self._async_select_address(
            "reconfigure_select_address", user_input, "reconfigure"
        )
