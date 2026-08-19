"""Config flow for the SpaceAPI integration."""

from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_EMAIL,
    CONF_ENTITY_ID,
    CONF_LOCATION,
    CONF_SENSORS,
    CONF_STATE,
    CONF_URL,
)
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CAM,
    CONF_CONTACT,
    CONF_FEED_FLICKR,
    CONF_FEEDS,
    CONF_ICON_CLOSED,
    CONF_ICON_OPEN,
    CONF_LOGO,
    CONF_PROJECTS,
    CONF_SPACE,
    CONF_SPACEFED,
    CONF_XMPP,
    DOMAIN,
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
        vol.Required(CONF_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(
                domain=["binary_sensor", "input_boolean", "switch", "lock", "cover"]
            )
        ),
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL)
        ),
    }
)

# Allowed feed type values per v15 spec
_FEED_TYPES = ["rss", "atom", "ical"]


class SpaceAPIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SpaceAPI."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        return self.async_create_entry(
            title=user_input[CONF_SPACE],
            data={
                CONF_SPACE: user_input[CONF_SPACE],
                CONF_LOGO: user_input[CONF_LOGO],
                CONF_URL: user_input[CONF_URL],
                CONF_STATE: {CONF_ENTITY_ID: user_input[CONF_ENTITY_ID]},
            },
            options={
                CONF_CONTACT: {CONF_EMAIL: user_input[CONF_EMAIL]},
            },
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import SpaceAPI config from YAML."""
        # Required fields -> entry.data
        data = {
            CONF_SPACE: import_data[CONF_SPACE],
            CONF_LOGO: import_data[CONF_LOGO],
            CONF_URL: import_data[CONF_URL],
            CONF_STATE: {CONF_ENTITY_ID: import_data[CONF_STATE][CONF_ENTITY_ID]},
        }

        # Optional fields -> entry.options
        options: dict[str, Any] = {}

        # Contact: keep all fields still valid in v15. "google" was removed in
        # v15 and "keymasters" is not a v15 contact field, so both are dropped
        # here. "jabber" is renamed to "xmpp".
        dropped_contact_fields = {"google", "keymasters"}
        contact: dict[str, Any] = {}
        for k, v in import_data.get(CONF_CONTACT, {}).items():
            if not v or k in dropped_contact_fields:
                continue
            if k == "jabber":
                contact[CONF_XMPP] = v
            else:
                contact[k] = v
        if contact:
            options[CONF_CONTACT] = contact

        # State icons
        state_icons: dict[str, str] = {}
        state_config = import_data.get(CONF_STATE, {})
        if CONF_ICON_OPEN in state_config:
            state_icons[CONF_ICON_OPEN] = state_config[CONF_ICON_OPEN]
        if CONF_ICON_CLOSED in state_config:
            state_icons[CONF_ICON_CLOSED] = state_config[CONF_ICON_CLOSED]
        if state_icons:
            options[CONF_STATE] = state_icons

        # Optional sections pass through directly (dropping removed v13 sections)
        for key in (CONF_SENSORS, CONF_CAM, CONF_PROJECTS):
            if key in import_data:
                options[key] = import_data[key]

        # Feeds: normalize flicker -> flickr (v15 spec key)
        if CONF_FEEDS in import_data:
            feeds = dict(import_data[CONF_FEEDS])
            if "flicker" in feeds:
                feeds[CONF_FEED_FLICKR] = feeds.pop("flicker")
            options[CONF_FEEDS] = feeds

        # Spacefed: drop spacephone
        if CONF_SPACEFED in import_data:
            spacefed = {
                k: v for k, v in import_data[CONF_SPACEFED].items() if k != "spacephone"
            }
            if spacefed:
                options[CONF_SPACEFED] = spacefed

        # Location address
        if CONF_LOCATION in import_data and CONF_ADDRESS in import_data[CONF_LOCATION]:
            options[CONF_LOCATION] = {
                CONF_ADDRESS: import_data[CONF_LOCATION][CONF_ADDRESS]
            }

        return self.async_create_entry(
            title=data[CONF_SPACE],
            data=data,
            options=options,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        entry = self._get_reconfigure_entry()
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA,
                    {
                        CONF_SPACE: entry.data[CONF_SPACE],
                        CONF_LOGO: entry.data[CONF_LOGO],
                        CONF_URL: entry.data[CONF_URL],
                        CONF_ENTITY_ID: entry.data[CONF_STATE][CONF_ENTITY_ID],
                        CONF_EMAIL: entry.options.get(CONF_CONTACT, {}).get(
                            CONF_EMAIL, ""
                        ),
                    },
                ),
            )

        # Email lives in options; merge it into the existing contact dict.
        updated_contact = {
            **entry.options.get(CONF_CONTACT, {}),
            CONF_EMAIL: user_input[CONF_EMAIL],
        }
        return self.async_update_and_abort(
            entry,
            title=user_input[CONF_SPACE],
            data_updates={
                CONF_SPACE: user_input[CONF_SPACE],
                CONF_LOGO: user_input[CONF_LOGO],
                CONF_URL: user_input[CONF_URL],
                CONF_STATE: {CONF_ENTITY_ID: user_input[CONF_ENTITY_ID]},
            },
            options={**entry.options, CONF_CONTACT: updated_contact},
        )
