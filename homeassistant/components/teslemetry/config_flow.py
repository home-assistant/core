"""Config Flow for Teslemetry integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientConnectionError
from tesla_fleet_api.exceptions import (
    InvalidToken,
    SubscriptionRequired,
    TeslaFleetError,
)
from tesla_fleet_api.teslemetry import Teslemetry

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLIENT_ID, DOMAIN, LOGGER


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Teslemetry OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 2

    def __init__(self) -> None:
        """Initialize config flow."""
        super().__init__()
        self.data: dict[str, Any] = {}
        self.uid: str | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return LOGGER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        await async_import_client_credential(
            self.hass,
            DOMAIN,
            ClientCredential(CLIENT_ID, "", name="Teslemetry"),
        )
        return await super().async_step_user()

    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle OAuth completion and create config entry."""
        self.data = data

        # Test the connection with the OAuth token
        errors = await self.async_test_connection(data)
        if errors:
            return self.async_abort(reason="oauth_error")

        await self.async_set_unique_id(self.uid)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="reauth_account_mismatch")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="Teslemetry",
            data=data,
        )

    async def async_test_connection(self, token_data: dict[str, Any]) -> dict[str, str]:
        """Test the connection with OAuth token."""
        access_token = token_data["token"]["access_token"]

        teslemetry = Teslemetry(
            session=async_get_clientsession(self.hass),
            access_token=access_token,
        )

        try:
            metadata = await teslemetry.metadata()
        except InvalidToken:
            return {"base": "invalid_access_token"}
        except SubscriptionRequired:
            return {"base": "subscription_required"}
        except ClientConnectionError:
            return {"base": "cannot_connect"}
        except TeslaFleetError as e:
            LOGGER.error("Teslemetry API error: %s", e)
            return {"base": "unknown"}

        self.uid = metadata["uid"]
        return {}

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth on failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={"name": "Teslemetry"},
            )

        return await super().async_step_user()
