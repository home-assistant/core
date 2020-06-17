"""Config flow for Withings."""
import logging
from typing import Dict, Optional

import voluptuous as vol
from withings_api.common import AuthScope

from homeassistant import config_entries
from homeassistant.components.withings import const
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.util import slugify

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
        errors = {}
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        context_profile = self.context.get(const.PROFILE)
        profile = data.get(const.PROFILE) or context_profile

        if profile:
            existing_entry = next(
                iter(
                    config_entry
                    for config_entry in self.hass.config_entries.async_entries(
                        const.DOMAIN
                    )
                    if slugify(config_entry.data.get(const.PROFILE)) == slugify(profile)
                ),
                None,
            )

            if context_profile or not existing_entry:
                new_data = {**self._current_data, **{const.PROFILE: profile}}
                self._current_data = None
                return await self.async_step_finish(new_data)

            errors["base"] = "profile_exists"

        return self.async_show_form(
            step_id="profile",
            data_schema=vol.Schema({vol.Required(const.PROFILE): str}),
            errors=errors,
        )

    async def async_step_reauth(self, data: Optional[Dict]) -> dict:
        """Prompt user to re-authenticate."""
        if data is not None:
            return await self.async_step_user()

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        placeholders = {"profile": self.context["profile"]}

        self.context.update({"title_placeholders": placeholders})

        return self.async_show_form(
            step_id="reauth",
            # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
            description_placeholders=placeholders,
        )

    async def async_step_finish(self, data: dict) -> dict:
        """Finish the flow."""
        self._current_data = None

        config_entry = await self.async_set_unique_id(
            str(data["token"]["userid"]), raise_on_progress=False
        )
        if config_entry:
            await self.hass.config_entries.async_remove(config_entry.entry_id)

        return self.async_create_entry(title=data[const.PROFILE], data=data)
