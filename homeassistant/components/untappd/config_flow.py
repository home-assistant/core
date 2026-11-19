"""Config flow for Untappd."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aiountappd import UntappdAuthenticationError, UntappdClient, UntappdError

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN


class UntappdOAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Untappd OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry after validating the account."""
        client = UntappdClient(
            async_get_clientsession(self.hass), data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        )
        try:
            user = await client.get_user_info()
        except UntappdAuthenticationError:
            return self.async_abort(reason="invalid_auth")
        except UntappdError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            self.logger.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(str(user.uid))
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=user.user_name, data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()
