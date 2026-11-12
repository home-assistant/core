"""Config flow for TRMNL."""

from collections.abc import Mapping
import logging
from typing import Any, override

import jwt
import probatio
from trmnl import TRMNLClient
from trmnl.exceptions import TRMNLAuthenticationError, TRMNLError

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import (
    CLIENT_ID,
    CONF_HOME_ENTITIES,
    DOMAIN,
    LOGGER,
    OAUTH2_SCOPES,
    REQUIRED_SCOPES,
)
from .coordinator import TRMNLConfigEntry, scope_granted
from .home import CAPABILITIES_BY_DOMAIN


class TRMNLConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """TRMNL config flow: sign in on trmnl.com."""

    DOMAIN = DOMAIN
    VERSION = 2

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: TRMNLConfigEntry) -> TRMNLOptionsFlow:
        """Return the options flow."""
        return TRMNLOptionsFlow()

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return the logger."""
        return LOGGER

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start the sign in on trmnl.com."""
        await async_import_client_credential(
            self.hass, DOMAIN, ClientCredential(CLIENT_ID, "", name="TRMNL")
        )
        return await super().async_step_user(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Sign in again, for example to grant a scope the user unticked before."""
        return await self.async_step_user()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to sign in again."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create the entry, or update it after reauth."""
        # The ID token comes straight from the token endpoint over TLS, so its signature needs no check.
        try:
            subject = jwt.decode(
                data["token"]["id_token"], options={"verify_signature": False}
            )["sub"]
        except KeyError, jwt.DecodeError:
            return self.async_abort(reason="missing_account_identity")

        # A token response without scope was granted every requested scope (RFC 6749 5.1).
        granted = set(data["token"].get("scope", OAUTH2_SCOPES).split())
        if not REQUIRED_SCOPES.issubset(granted):
            return self.async_abort(reason="missing_scopes")

        client = TRMNLClient(
            token=data["token"]["access_token"],
            session=async_get_clientsession(self.hass),
        )
        try:
            await client.get_devices()
            user = await client.get_me() if "profile" in granted else None
        except TRMNLAuthenticationError:
            return self.async_abort(reason="oauth_unauthorized")
        except TRMNLError, TimeoutError:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(subject)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )
        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data=data
            )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=user.name if user else "TRMNL", data=data)


class TRMNLOptionsFlow(OptionsFlowWithReload):
    """TRMNL options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the entities to show on TRMNL."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_HOME_ENTITIES] and not scope_granted(
                self.config_entry, "content"
            ):
                errors["base"] = "content_not_granted"
            else:
                return self.async_create_entry(
                    data={**self.config_entry.options, **user_input}
                )
        schema = probatio.Schema(
            {
                probatio.Optional(
                    CONF_HOME_ENTITIES,
                    default=self.config_entry.options.get(CONF_HOME_ENTITIES, []),
                ): EntitySelector(
                    EntitySelectorConfig(
                        domain=list(CAPABILITIES_BY_DOMAIN), multiple=True
                    )
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
