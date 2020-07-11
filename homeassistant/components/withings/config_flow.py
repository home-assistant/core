"""Config flow for Withings."""
import logging
from typing import Dict, Union

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
    # Temporarily holds authorization data during the profile step.
    _current_data: Dict[str, Union[None, str, int]] = {}

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
        reauth_profile = (
            self.context.get(const.PROFILE)
            if self.context.get("source") == "reauth"
            else None
        )
        profile = data.get(const.PROFILE) or reauth_profile

        if profile:
            existing_entries = [
                config_entry
                for config_entry in self.hass.config_entries.async_entries(const.DOMAIN)
                if slugify(config_entry.data.get(const.PROFILE)) == slugify(profile)
            ]

            if reauth_profile or not existing_entries:
                new_data = {**self._current_data, **data, const.PROFILE: profile}
                self._current_data = {}
                return await self.async_step_finish(new_data)

            errors["base"] = "profile_exists"

        return self.async_show_form(
            step_id="profile",
            data_schema=vol.Schema({vol.Required(const.PROFILE): str}),
            errors=errors,
        )

    async def async_step_reauth(self, data: dict = None) -> dict:
        """Prompt user to re-authenticate."""
        if data is not None:
            return await self.async_step_user()

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        placeholders = {const.PROFILE: self.context["profile"]}

        self.context.update({"title_placeholders": placeholders})

        return self.async_show_form(
            step_id="reauth",
            # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
            description_placeholders=placeholders,
        )

    async def async_step_finish(self, data: dict) -> dict:
        """Finish the flow."""
        self._current_data = {}

        await self.async_set_unique_id(
            str(data["token"]["userid"]), raise_on_progress=False
        )
        self._abort_if_unique_id_configured(data)

        return self.async_create_entry(title=data[const.PROFILE], data=data)
