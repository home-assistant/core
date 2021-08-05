"""Config flow to configure the Toon component."""
from __future__ import annotations

import logging
from typing import Any

from toonapi import Agreement, Toon, ToonError
import voluptuous as vol

from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import CONF_AGREEMENT, CONF_AGREEMENT_ID, CONF_MIGRATE, DOMAIN


class ToonFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a Toon config flow."""

    DOMAIN = DOMAIN
    VERSION = 2

    agreements: list[Agreement] | None = None
    data: dict[str, Any] | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Test connection and load up agreements."""
        self.data = data

        toon = Toon(
            token=self.data["token"]["access_token"],
            session=async_get_clientsession(self.hass),
        )
        try:
            self.agreements = await toon.agreements()
        except ToonError:
            return self.async_abort(reason="connection_error")

        if not self.agreements:
            return self.async_abort(reason="no_agreements")

        return await self.async_step_agreement()

    async def async_step_import(
        self, config: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start a configuration flow based on imported data.

        This step is merely here to trigger "discovery" when the `toon`
        integration is listed in the user configuration, or when migrating from
        the version 1 schema.
        """

        if config is not None and CONF_MIGRATE in config:
            self.context.update({CONF_MIGRATE: config[CONF_MIGRATE]})
        else:
            await self._async_handle_discovery_without_unique_id()

        return await self.async_step_user()

    async def async_step_agreement(
        self, user_input: dict[str, Any] = None
    ) -> FlowResult:
        """Select Toon agreement to add."""
        if len(self.agreements) == 1:
            return await self._create_entry(self.agreements[0])

        agreements_list = [
            f"{agreement.street} {agreement.house_number}, {agreement.city}"
            for agreement in self.agreements
        ]

        if user_input is None:
            return self.async_show_form(
                step_id="agreement",
                data_schema=vol.Schema(
                    {vol.Required(CONF_AGREEMENT): vol.In(agreements_list)}
                ),
            )

        agreement_index = agreements_list.index(user_input[CONF_AGREEMENT])
        return await self._create_entry(self.agreements[agreement_index])

    async def _create_entry(self, agreement: Agreement) -> FlowResult:
        if CONF_MIGRATE in self.context:
            await self.hass.config_entries.async_remove(self.context[CONF_MIGRATE])

        await self.async_set_unique_id(agreement.agreement_id)
        self._abort_if_unique_id_configured()

        self.data[CONF_AGREEMENT_ID] = agreement.agreement_id
        return self.async_create_entry(
            title=f"{agreement.street} {agreement.house_number}, {agreement.city}",
            data=self.data,
        )
