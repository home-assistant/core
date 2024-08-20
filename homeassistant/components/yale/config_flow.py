"""Config flow for Yale integration."""

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class YaleConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a config flow for Yale."""

    VERSION = 1
    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Instantiate config flow."""
        self.reauth_entry: config_entries.ConfigEntry | None = None
        super().__init__()

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    async def async_step_reauth(
        self, data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle configuration by re-auth."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(data["entry_id"])
        return await self.async_step_user()

    async def async_oauth_create_entry(
        self, data: dict
    ) -> config_entries.ConfigFlowResult:
        """Create an entry for the flow."""
        if entry := self.reauth_entry:
            return self.async_update_reload_and_abort(entry, data=data)
        return self.async_create_entry(title=self.flow_impl.name, data=data)
