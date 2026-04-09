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

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import SpaceAPI config from YAML."""
        self._async_abort_entries_match({})

        # Required fields -> entry.data
        data = {
            CONF_SPACE: import_data[CONF_SPACE],
            CONF_LOGO: import_data[CONF_LOGO],
            CONF_URL: import_data[CONF_URL],
            "state": {"entity_id": import_data["state"]["entity_id"]},
            CONF_CONTACT: {CONF_EMAIL: import_data[CONF_CONTACT].get(CONF_EMAIL, "")},
            CONF_ISSUE_REPORT_CHANNELS: import_data[CONF_ISSUE_REPORT_CHANNELS],
        }

        # Optional fields -> entry.options
        options: dict[str, Any] = {}

        # Contact extras (everything except email)
        contact_extras = {
            k: v
            for k, v in import_data.get(CONF_CONTACT, {}).items()
            if k != CONF_EMAIL and v
        }
        if contact_extras:
            options[CONF_CONTACT] = contact_extras

        # State icons
        state_icons: dict[str, str] = {}
        state_config = import_data.get("state", {})
        if "icon_open" in state_config:
            state_icons["icon_open"] = state_config["icon_open"]
        if "icon_closed" in state_config:
            state_icons["icon_closed"] = state_config["icon_closed"]
        if state_icons:
            options["state"] = state_icons

        # Optional sections pass through directly
        for key in (
            "sensors",
            "spacefed",
            "cam",
            "stream",
            "feeds",
            "cache",
            "projects",
            "radio_show",
        ):
            if key in import_data:
                options[key] = import_data[key]

        # Location address
        if "location" in import_data and "address" in import_data["location"]:
            options["location"] = {"address": import_data["location"]["address"]}

        return self.async_create_entry(
            title=data[CONF_SPACE],
            data=data,
            options=options,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        if user_input is None:
            entry = self._get_reconfigure_entry()
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA,
                    {
                        CONF_SPACE: entry.data[CONF_SPACE],
                        CONF_LOGO: entry.data[CONF_LOGO],
                        CONF_URL: entry.data[CONF_URL],
                        "entity_id": entry.data["state"]["entity_id"],
                        CONF_EMAIL: entry.data[CONF_CONTACT][CONF_EMAIL],
                        CONF_ISSUE_REPORT_CHANNELS: entry.data[
                            CONF_ISSUE_REPORT_CHANNELS
                        ],
                    },
                ),
            )

        entry = self._get_reconfigure_entry()
        return self.async_update_reload_and_abort(
            entry,
            title=user_input[CONF_SPACE],
            data_updates={
                CONF_SPACE: user_input[CONF_SPACE],
                CONF_LOGO: user_input[CONF_LOGO],
                CONF_URL: user_input[CONF_URL],
                "state": {
                    "entity_id": user_input["entity_id"],
                    **{
                        k: v
                        for k, v in entry.data.get("state", {}).items()
                        if k != "entity_id"
                    },
                },
                CONF_CONTACT: {
                    CONF_EMAIL: user_input[CONF_EMAIL],
                    **{
                        k: v
                        for k, v in entry.data.get(CONF_CONTACT, {}).items()
                        if k != CONF_EMAIL
                    },
                },
                CONF_ISSUE_REPORT_CHANNELS: user_input[CONF_ISSUE_REPORT_CHANNELS],
            },
        )
