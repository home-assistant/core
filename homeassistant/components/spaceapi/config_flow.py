"""Config flow for the SpaceAPI integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_URL
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CONTACT,
    CONF_ISSUE_REPORT_CHANNELS,
    CONF_LOGO,
    CONF_SPACE,
    DOMAIN,
    ISSUE_REPORT_CHANNELS,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SPACE): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_LOGO): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required("entity_id"): EntitySelector(EntitySelectorConfig()),
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL)
        ),
        vol.Required(CONF_ISSUE_REPORT_CHANNELS): SelectSelector(
            SelectSelectorConfig(
                options=ISSUE_REPORT_CHANNELS,
                multiple=True,
                translation_key="issue_report_channels",
            )
        ),
    }
)


class SpaceAPIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SpaceAPI."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        self._async_abort_entries_match({})

        return self.async_create_entry(
            title=user_input[CONF_SPACE],
            data={
                CONF_SPACE: user_input[CONF_SPACE],
                CONF_LOGO: user_input[CONF_LOGO],
                CONF_URL: user_input[CONF_URL],
                "state": {"entity_id": user_input["entity_id"]},
                CONF_CONTACT: {CONF_EMAIL: user_input[CONF_EMAIL]},
                CONF_ISSUE_REPORT_CHANNELS: user_input[CONF_ISSUE_REPORT_CHANNELS],
            },
        )
