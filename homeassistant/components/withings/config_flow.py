"""Config flow for Withings."""
import logging

import voluptuous as vol
from withings_api.common import AuthScope

from homeassistant import config_entries
from homeassistant.components.withings import const
from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(const.DOMAIN)
class WithingsFlowHandler(config_entry_oauth2_flow.AbstractOAuth2FlowHandler):
    """Handle a config flow."""

    DOMAIN = const.DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    _current_data = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": ",".join(
                [
                    AuthScope.USER_INFO.value,
                    AuthScope.USER_METRICS.value,
                    AuthScope.USER_ACTIVITY.value,
                ]
            )
        }

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Override the create entry so user can select a profile."""
        self._current_data = data
        return await self.async_step_profile(data)

    async def async_step_profile(self, data: dict) -> dict:
        """Prompt the user to select a user profile."""
        profile = data.get(const.PROFILE)

        if profile:
            new_data = {**self._current_data, **{const.PROFILE: profile}}
            self._current_data = None
            return await self.async_step_finish(new_data)

        profiles = self.hass.data[const.DOMAIN][const.CONFIG][const.CONF_PROFILES]
        return self.async_show_form(
            step_id="profile",
            data_schema=vol.Schema({vol.Required(const.PROFILE): vol.In(profiles)}),
        )

    async def async_step_finish(self, data: dict) -> dict:
        """Finish the flow."""
        self._current_data = None

        return self.async_create_entry(title=data[const.PROFILE], data=data)
