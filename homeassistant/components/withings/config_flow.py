"""Config flow for Withings."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from withings_api.common import AuthScope

from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.util import slugify

from . import const


class WithingsFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=const.DOMAIN
):
    """Handle a config flow."""

    DOMAIN = const.DOMAIN

    # Temporarily holds authorization data during the profile step.
    _current_data: dict[str, None | str | int] = {}
    _reauth_profile: str | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, str]:
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

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Override the create entry so user can select a profile."""
        self._current_data = data
        return await self.async_step_profile(data)

    async def async_step_profile(self, data: dict[str, Any]) -> FlowResult:
        """Prompt the user to select a user profile."""
        errors = {}
        profile = data.get(const.PROFILE) or self._reauth_profile

        if profile:
            existing_entries = [
                config_entry
                for config_entry in self._async_current_entries()
                if slugify(config_entry.data.get(const.PROFILE)) == slugify(profile)
            ]

            if self._reauth_profile or not existing_entries:
                new_data = {**self._current_data, **data, const.PROFILE: profile}
                self._current_data = {}
                return await self.async_step_finish(new_data)

            errors["base"] = "already_configured"

        return self.async_show_form(
            step_id="profile",
            data_schema=vol.Schema({vol.Required(const.PROFILE): str}),
            errors=errors,
        )

    async def async_step_reauth(self, data: Mapping[str, Any]) -> FlowResult:
        """Prompt user to re-authenticate."""
        self._reauth_profile = data.get(const.PROFILE)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, data: dict[str, Any] | None = None
    ) -> FlowResult:
        """Prompt user to re-authenticate."""
        if data is not None:
            return await self.async_step_user()

        placeholders = {const.PROFILE: self._reauth_profile}

        self.context.update({"title_placeholders": placeholders})

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders=placeholders,
        )

    async def async_step_finish(self, data: dict[str, Any]) -> FlowResult:
        """Finish the flow."""
        self._current_data = {}

        await self.async_set_unique_id(
            str(data["token"]["userid"]), raise_on_progress=False
        )
        self._abort_if_unique_id_configured(data)

        return self.async_create_entry(title=data[const.PROFILE], data=data)
