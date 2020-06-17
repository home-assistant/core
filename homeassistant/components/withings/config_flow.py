"""Config flow for Withings."""
import logging

import voluptuous as vol
from withings_api.common import AuthScope

from homeassistant import config_entries
from homeassistant.components.withings import const
from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)


class WithingsFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=const.DOMAIN
):
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
                    AuthScope.USER_SLEEP_EVENTS.value,
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

        return self.async_show_form(
            step_id="profile",
            data_schema=vol.Schema({vol.Required(const.PROFILE): str}),
        )

    async def async_step_reauth(self, data: dict) -> dict:
        """Prompt user to re-authenticate."""
        if data is not None:
            return await self.async_step_user()

        return self.async_show_form(
            step_id="reauth",
            # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
            description_placeholders={"profile": self.context["profile"]},
        )

    async def async_step_finish(self, data: dict) -> dict:
        """Finish the flow."""
        self._current_data = None

        await self.async_set_unique_id(data["token"]["userid"], raise_on_progress=False)
        return self.async_create_entry(title=data[const.PROFILE], data=data)
