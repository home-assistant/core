"""Config flow to configure Heiman."""

import logging
from typing import Any, override

from heimanconnect import HeimanAuthError, HeimanTokenExpiredError

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .api import HeimanApiClient
from .const import CONF_USER_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HeimanConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle configuration of Heiman integration."""

    DOMAIN = DOMAIN

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {}

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry covering every home on the account."""
        api_client = HeimanApiClient(
            hass=self.hass, session=None, token_data=data[CONF_TOKEN]
        )

        try:
            await api_client.initialize()

            try:
                user_info = await api_client.cloud_client.async_get_user_info()
                homes = await api_client.cloud_client.async_get_homes()
                if not homes:
                    return self.async_abort(reason="no_homes")
            except HeimanTokenExpiredError:
                return self.async_abort(reason="token_expired")
            except HeimanAuthError:
                return self.async_abort(reason="token_invalid")
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Failed to fetch account information: %s", err)
                return self.async_abort(reason="account_info_failed")

            await self.async_set_unique_id(user_info.user_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_info.get_display_name() or "Heiman Home",
                data={
                    **data,
                    CONF_USER_ID: user_info.user_id,
                },
            )
        finally:
            await api_client.close()
