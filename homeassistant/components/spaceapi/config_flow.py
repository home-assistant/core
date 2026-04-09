"""Config flow for the SpaceAPI integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import SpaceAPIConfigEntry
from .const import (
    CONF_CAM,
    CONF_CONTACT,
    CONF_FACEBOOK,
    CONF_FEED_BLOG,
    CONF_FEED_CALENDAR,
    CONF_FEED_FLICKER,
    CONF_FEED_WIKI,
    CONF_FEEDS,
    CONF_GOPHER,
    CONF_HUMIDITY,
    CONF_ICON_CLOSED,
    CONF_ICON_OPEN,
    CONF_IRC,
    CONF_LOGO,
    CONF_MASTODON,
    CONF_MATRIX,
    CONF_ML,
    CONF_MUMBLE,
    CONF_PHONE,
    CONF_PROJECTS,
    CONF_SIP,
    CONF_SPACE,
    CONF_SPACEFED,
    CONF_SPACENET,
    CONF_SPACESAML,
    CONF_TEMPERATURE,
    CONF_TWITTER,
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
        vol.Required("entity_id"): EntitySelector(
            EntitySelectorConfig(
                domain=["binary_sensor", "input_boolean", "switch", "lock", "cover"]
            )
        ),
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL)
        ),
    }
)


class SpaceAPIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SpaceAPI."""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: SpaceAPIConfigEntry,
    ) -> SpaceAPIOptionsFlowHandler:
        """Create the options flow."""
        return SpaceAPIOptionsFlowHandler()

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
        }

        # Optional fields -> entry.options
        options: dict[str, Any] = {}

        # Contact extras (everything except email, dropping removed v13 fields)
        dropped_contact_fields = {"identica", "foursquare", "issue_mail", "keymasters"}
        contact_extras: dict[str, Any] = {}
        for k, v in import_data.get(CONF_CONTACT, {}).items():
            if k == CONF_EMAIL or not v or k in dropped_contact_fields:
                continue
            # Auto-rename jabber -> xmpp
            if k == "jabber":
                contact_extras[CONF_XMPP] = v
            else:
                contact_extras[k] = v
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

        # Optional sections pass through directly (dropping removed v13 sections)
        for key in (
            "sensors",
            "cam",
            "feeds",
            "projects",
        ):
            if key in import_data:
                options[key] = import_data[key]

        # Spacefed: drop spacephone
        if "spacefed" in import_data:
            spacefed = {
                k: v for k, v in import_data["spacefed"].items() if k != "spacephone"
            }
            if spacefed:
                options["spacefed"] = spacefed

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
            },
        )


class SpaceAPIOptionsFlowHandler(OptionsFlow):
    """Handle SpaceAPI options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "contact",
                "state_icons",
                "sensors",
                "spacefed",
                "media",
                "feeds",
                "other",
            ],
        )

    async def async_step_contact(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure contact details."""
        if user_input is not None:
            options = dict(self.config_entry.options)
            contact = {k: v for k, v in user_input.items() if v}
            if contact:
                options[CONF_CONTACT] = contact
            else:
                options.pop(CONF_CONTACT, None)
            return self.async_create_entry(data=options)

        current = self.config_entry.options.get(CONF_CONTACT, {})
        schema = vol.Schema(
            {
                vol.Optional(CONF_EMAIL, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.EMAIL)
                ),
                vol.Optional(CONF_IRC, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_ML, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_PHONE, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_SIP, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_TWITTER, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_FACEBOOK, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_MASTODON, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_MATRIX, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_XMPP, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_MUMBLE, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_GOPHER, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
            }
        )
        return self.async_show_form(
            step_id="contact",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )

    async def async_step_state_icons(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure state icons."""
        if user_input is not None:
            options = dict(self.config_entry.options)
            state_icons = {k: v for k, v in user_input.items() if v}
            if state_icons:
                options["state"] = state_icons
            else:
                options.pop("state", None)
            return self.async_create_entry(data=options)

        current = self.config_entry.options.get("state", {})
        schema = vol.Schema(
            {
                vol.Optional(CONF_ICON_OPEN, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Optional(CONF_ICON_CLOSED, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
            }
        )
        return self.async_show_form(
            step_id="state_icons",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure sensors."""
        if user_input is not None:
            options = dict(self.config_entry.options)
            sensors = {k: v for k, v in user_input.items() if v}
            if sensors:
                options["sensors"] = sensors
            else:
                options.pop("sensors", None)
            return self.async_create_entry(data=options)

        current = self.config_entry.options.get("sensors", {})
        schema = vol.Schema(
            {
                vol.Optional(CONF_TEMPERATURE): EntitySelector(
                    EntitySelectorConfig(multiple=True)
                ),
                vol.Optional(CONF_HUMIDITY): EntitySelector(
                    EntitySelectorConfig(multiple=True)
                ),
            }
        )
        return self.async_show_form(
            step_id="sensors",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )

    async def async_step_spacefed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure space federation."""
        if user_input is not None:
            options = dict(self.config_entry.options)
            spacefed = dict(user_input)
            if any(spacefed.values()):
                options[CONF_SPACEFED] = spacefed
            else:
                options.pop(CONF_SPACEFED, None)
            return self.async_create_entry(data=options)

        current = self.config_entry.options.get(CONF_SPACEFED, {})
        schema = vol.Schema(
            {
                vol.Required(CONF_SPACENET, default=False): BooleanSelector(),
                vol.Required(CONF_SPACESAML, default=False): BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="spacefed",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )

    async def async_step_media(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure media (cameras)."""
        if user_input is not None:
            options = dict(self.config_entry.options)

            # Camera URLs
            cam_urls = user_input.get(CONF_CAM, [])
            if cam_urls:
                options[CONF_CAM] = cam_urls
            else:
                options.pop(CONF_CAM, None)

            return self.async_create_entry(data=options)

        current_cam = self.config_entry.options.get(CONF_CAM, [])
        current = {
            CONF_CAM: current_cam,
        }
        schema = vol.Schema(
            {
                vol.Optional(CONF_CAM): SelectSelector(
                    SelectSelectorConfig(options=[], custom_value=True, multiple=True)
                ),
            }
        )
        return self.async_show_form(
            step_id="media",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )

    async def async_step_feeds(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure feeds."""
        if user_input is not None:
            options = dict(self.config_entry.options)
            feeds: dict[str, dict[str, str]] = {}

            for feed_name in (
                CONF_FEED_BLOG,
                CONF_FEED_WIKI,
                CONF_FEED_CALENDAR,
                CONF_FEED_FLICKER,
            ):
                url = user_input.get(f"{feed_name}_url", "")
                feed_type = user_input.get(f"{feed_name}_type", "")
                if url:
                    feed_entry: dict[str, str] = {"url": url}
                    if feed_type:
                        feed_entry["type"] = feed_type
                    feeds[feed_name] = feed_entry

            if feeds:
                options[CONF_FEEDS] = feeds
            else:
                options.pop(CONF_FEEDS, None)
            return self.async_create_entry(data=options)

        current_feeds = self.config_entry.options.get(CONF_FEEDS, {})
        current: dict[str, str] = {}
        for feed_name in (
            CONF_FEED_BLOG,
            CONF_FEED_WIKI,
            CONF_FEED_CALENDAR,
            CONF_FEED_FLICKER,
        ):
            feed_data = current_feeds.get(feed_name, {})
            current[f"{feed_name}_url"] = feed_data.get("url", "")
            current[f"{feed_name}_type"] = feed_data.get("type", "")

        schema = vol.Schema(
            {
                vol.Optional("blog_url", default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Optional("blog_type", default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional("wiki_url", default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Optional("wiki_type", default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional("calendar_url", default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Optional("calendar_type", default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional("flicker_url", default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Optional("flicker_type", default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
            }
        )
        return self.async_show_form(
            step_id="feeds",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )

    async def async_step_other(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure other settings (projects)."""
        if user_input is not None:
            options = dict(self.config_entry.options)

            projects = user_input.get(CONF_PROJECTS, [])
            if projects:
                options[CONF_PROJECTS] = projects
            else:
                options.pop(CONF_PROJECTS, None)

            return self.async_create_entry(data=options)

        current_projects = self.config_entry.options.get(CONF_PROJECTS, [])
        current = {
            CONF_PROJECTS: current_projects,
        }
        schema = vol.Schema(
            {
                vol.Optional(CONF_PROJECTS): SelectSelector(
                    SelectSelectorConfig(options=[], custom_value=True, multiple=True)
                ),
            }
        )
        return self.async_show_form(
            step_id="other",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )
