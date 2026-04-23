"""Config flow for the SpaceAPI integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_EMAIL,
    CONF_ENTITY_ID,
    CONF_LOCATION,
    CONF_SENSORS,
    CONF_STATE,
    CONF_URL,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import SpaceAPIConfigEntry
from .const import (
    BILLING_INTERVALS,
    CONF_ACCOUNT_BALANCE,
    CONF_ACTIVITIES,
    CONF_AREA_DESCRIPTION,
    CONF_AREA_NAME,
    CONF_AREA_SQUARE_METERS,
    CONF_BAROMETER,
    CONF_BEVERAGE_SUPPLY,
    CONF_CAM,
    CONF_CARBONDIOXIDE,
    CONF_CONTACT,
    CONF_COUNTRY_CODE,
    CONF_DOOR_LOCKED,
    CONF_EVENTS_WINDOW_HOURS,
    CONF_FACEBOOK,
    CONF_FEED_BLOG,
    CONF_FEED_CALENDAR,
    CONF_FEED_FLICKR,
    CONF_FEED_WIKI,
    CONF_FEEDS,
    CONF_GOPHER,
    CONF_HINT,
    CONF_HUMIDITY,
    CONF_ICON_CLOSED,
    CONF_ICON_OPEN,
    CONF_IRC,
    CONF_LINK_DESCRIPTION,
    CONF_LINK_NAME,
    CONF_LINK_URL,
    CONF_LINKED_SPACE_ENDPOINT,
    CONF_LINKED_SPACE_WEBSITE,
    CONF_LOGO,
    CONF_MASTODON,
    CONF_MATRIX,
    CONF_MESSAGE,
    CONF_ML,
    CONF_MUMBLE,
    CONF_NETWORK_CONNECTIONS,
    CONF_NETWORK_TRAFFIC,
    CONF_PEOPLE_NOW_PRESENT,
    CONF_PHONE,
    CONF_PLAN_BILLING_INTERVAL,
    CONF_PLAN_CURRENCY,
    CONF_PLAN_DESCRIPTION,
    CONF_PLAN_NAME,
    CONF_PLAN_VALUE,
    CONF_POWER_CONSUMPTION,
    CONF_POWER_GENERATION,
    CONF_PROJECTS,
    CONF_RADIATION,
    CONF_SIP,
    CONF_SPACE,
    CONF_SPACEFED,
    CONF_SPACENET,
    CONF_SPACESAML,
    CONF_TEMPERATURE,
    CONF_TIMEZONE,
    CONF_TOTAL_MEMBER_COUNT,
    CONF_TWITTER,
    CONF_WIND_DIRECTION,
    CONF_WIND_ELEVATION,
    CONF_WIND_GUST,
    CONF_WIND_LOCATION,
    CONF_WIND_NAME,
    CONF_WIND_SPEED,
    CONF_XMPP,
    DOMAIN,
    SUBENTRY_LINK,
    SUBENTRY_LINKED_SPACE,
    SUBENTRY_LOCATION_AREA,
    SUBENTRY_MEMBERSHIP_PLAN,
    SUBENTRY_WIND_SENSOR,
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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: SpaceAPIConfigEntry,
    ) -> SpaceAPIOptionsFlowHandler:
        """Create the options flow."""
        return SpaceAPIOptionsFlowHandler()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry types supported by SpaceAPI."""
        return {
            SUBENTRY_LINK: LinkSubentryFlowHandler,
            SUBENTRY_MEMBERSHIP_PLAN: MembershipPlanSubentryFlowHandler,
            SUBENTRY_LINKED_SPACE: LinkedSpaceSubentryFlowHandler,
            SUBENTRY_LOCATION_AREA: LocationAreaSubentryFlowHandler,
            SUBENTRY_WIND_SENSOR: WindSensorSubentryFlowHandler,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

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
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Required fields -> entry.data
        data = {
            CONF_SPACE: import_data[CONF_SPACE],
            CONF_LOGO: import_data[CONF_LOGO],
            CONF_URL: import_data[CONF_URL],
            CONF_STATE: {CONF_ENTITY_ID: import_data[CONF_STATE][CONF_ENTITY_ID]},
        }

        # Optional fields -> entry.options
        options: dict[str, Any] = {}

        # Contact: email + extras all go to options; drop removed v13 fields
        dropped_contact_fields = {"identica", "foursquare", "issue_mail", "keymasters"}
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
        return self.async_update_reload_and_abort(
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
                "state_extras",
                "sensors",
                "spacefed",
                "location",
                "media",
                "feeds",
                "events",
                "projects",
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
                    TextSelectorConfig(type=TextSelectorType.EMAIL)
                ),
                vol.Optional(CONF_PHONE, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEL)
                ),
                vol.Optional(CONF_SIP, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Optional(CONF_TWITTER, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_FACEBOOK, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
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
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Optional(CONF_GOPHER, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
            }
        )
        return self.async_show_form(
            step_id="contact",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )

    async def async_step_state_extras(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure state icons and optional state text fields."""
        if user_input is not None:
            options = dict(self.config_entry.options)
            state_extras = {k: v for k, v in user_input.items() if v}
            if state_extras:
                options[CONF_STATE] = state_extras
            else:
                options.pop(CONF_STATE, None)
            return self.async_create_entry(data=options)

        current = self.config_entry.options.get(CONF_STATE, {})
        schema = vol.Schema(
            {
                vol.Optional(CONF_ICON_OPEN, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Optional(CONF_ICON_CLOSED, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Optional(CONF_MESSAGE): EntitySelector(
                    EntitySelectorConfig(domain=["input_text", "text", "sensor"])
                ),
            }
        )
        return self.async_show_form(
            step_id="state_extras",
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
                options[CONF_SENSORS] = sensors
            else:
                options.pop(CONF_SENSORS, None)
            return self.async_create_entry(data=options)

        current = self.config_entry.options.get(CONF_SENSORS, {})
        schema = vol.Schema(
            {
                vol.Optional(CONF_TEMPERATURE): EntitySelector(
                    EntitySelectorConfig(
                        multiple=True,
                        domain="sensor",
                        device_class="temperature",
                    )
                ),
                vol.Optional(CONF_HUMIDITY): EntitySelector(
                    EntitySelectorConfig(
                        multiple=True,
                        domain="sensor",
                        device_class="humidity",
                    )
                ),
                vol.Optional(CONF_BAROMETER): EntitySelector(
                    EntitySelectorConfig(
                        multiple=True,
                        domain="sensor",
                        device_class="atmospheric_pressure",
                    )
                ),
                vol.Optional(CONF_CARBONDIOXIDE): EntitySelector(
                    EntitySelectorConfig(
                        multiple=True,
                        domain="sensor",
                        device_class="carbon_dioxide",
                    )
                ),
                vol.Optional(CONF_RADIATION): EntitySelector(
                    EntitySelectorConfig(
                        multiple=True,
                        domain="sensor",
                    )
                ),
                vol.Optional(CONF_POWER_CONSUMPTION): EntitySelector(
                    EntitySelectorConfig(
                        multiple=True,
                        domain="sensor",
                        device_class="power",
                    )
                ),
                vol.Optional(CONF_POWER_GENERATION): EntitySelector(
                    EntitySelectorConfig(
                        multiple=True,
                        domain="sensor",
                        device_class="power",
                    )
                ),
                vol.Optional(CONF_DOOR_LOCKED): EntitySelector(
                    EntitySelectorConfig(
                        multiple=True,
                        domain=["lock", "binary_sensor"],
                    )
                ),
                vol.Optional(CONF_PEOPLE_NOW_PRESENT): EntitySelector(
                    EntitySelectorConfig(
                        multiple=True,
                        domain="sensor",
                    )
                ),
                vol.Optional(CONF_TOTAL_MEMBER_COUNT): EntitySelector(
                    EntitySelectorConfig(
                        multiple=True,
                        domain="sensor",
                    )
                ),
                vol.Optional(CONF_ACCOUNT_BALANCE): EntitySelector(
                    EntitySelectorConfig(
                        multiple=True,
                        domain="sensor",
                        device_class="monetary",
                    )
                ),
                vol.Optional(CONF_BEVERAGE_SUPPLY): EntitySelector(
                    EntitySelectorConfig(
                        multiple=True,
                        domain="sensor",
                    )
                ),
                vol.Optional(CONF_NETWORK_CONNECTIONS): EntitySelector(
                    EntitySelectorConfig(
                        multiple=True,
                        domain="sensor",
                    )
                ),
                vol.Optional(CONF_NETWORK_TRAFFIC): EntitySelector(
                    EntitySelectorConfig(
                        multiple=True,
                        domain="sensor",
                    )
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

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure location details."""
        if user_input is not None:
            options = dict(self.config_entry.options)
            location = {k: v for k, v in user_input.items() if v}
            if location:
                options[CONF_LOCATION] = location
            else:
                options.pop(CONF_LOCATION, None)
            return self.async_create_entry(data=options)

        current = self.config_entry.options.get(CONF_LOCATION, {})
        schema = vol.Schema(
            {
                vol.Optional("address", default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_TIMEZONE, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_COUNTRY_CODE, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_HINT, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
            }
        )
        return self.async_show_form(
            step_id="location",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )

    async def async_step_media(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure media (cameras)."""
        if user_input is not None:
            options = dict(self.config_entry.options)

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
                CONF_FEED_FLICKR,
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
        # Normalize legacy "flicker" key to "flickr" on first edit
        if "flicker" in current_feeds and CONF_FEED_FLICKR not in current_feeds:
            current_feeds = dict(current_feeds)
            current_feeds[CONF_FEED_FLICKR] = current_feeds.pop("flicker")

        current: dict[str, str] = {}
        for feed_name in (
            CONF_FEED_BLOG,
            CONF_FEED_WIKI,
            CONF_FEED_CALENDAR,
            CONF_FEED_FLICKR,
        ):
            feed_data = current_feeds.get(feed_name, {})
            current[f"{feed_name}_url"] = feed_data.get("url", "")
            current[f"{feed_name}_type"] = feed_data.get("type", "")

        schema = vol.Schema(
            {
                vol.Optional("blog_url", default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Optional("blog_type", default=""): SelectSelector(
                    SelectSelectorConfig(options=_FEED_TYPES, custom_value=True)
                ),
                vol.Optional("wiki_url", default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Optional("wiki_type", default=""): SelectSelector(
                    SelectSelectorConfig(options=_FEED_TYPES, custom_value=True)
                ),
                vol.Optional("calendar_url", default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Optional("calendar_type", default=""): SelectSelector(
                    SelectSelectorConfig(options=_FEED_TYPES, custom_value=True)
                ),
                vol.Optional("flickr_url", default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Optional("flickr_type", default=""): SelectSelector(
                    SelectSelectorConfig(options=_FEED_TYPES, custom_value=True)
                ),
            }
        )
        return self.async_show_form(
            step_id="feeds",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )

    async def async_step_events(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure activity entities published as SpaceAPI events."""
        if user_input is not None:
            options = dict(self.config_entry.options)
            activities = user_input.get(CONF_ACTIVITIES, [])
            if activities:
                options[CONF_ACTIVITIES] = activities
            else:
                options.pop(CONF_ACTIVITIES, None)
            if (hours := user_input.get(CONF_EVENTS_WINDOW_HOURS)) is not None:
                options[CONF_EVENTS_WINDOW_HOURS] = int(hours)
            else:
                options.pop(CONF_EVENTS_WINDOW_HOURS, None)
            return self.async_create_entry(data=options)

        current = {
            CONF_ACTIVITIES: self.config_entry.options.get(CONF_ACTIVITIES, []),
            CONF_EVENTS_WINDOW_HOURS: self.config_entry.options.get(
                CONF_EVENTS_WINDOW_HOURS
            ),
        }
        schema = vol.Schema(
            {
                vol.Optional(CONF_ACTIVITIES): EntitySelector(
                    EntitySelectorConfig(multiple=True)
                ),
                vol.Optional(CONF_EVENTS_WINDOW_HOURS): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=8760,
                        step=1,
                        unit_of_measurement="h",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="events",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )

    async def async_step_projects(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure projects."""
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
            step_id="projects",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )


class LinkSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding/editing links."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new link subentry."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_LINK_NAME],
                data=user_input,
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LINK_NAME): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    ),
                    vol.Required(CONF_LINK_URL): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.URL)
                    ),
                    vol.Optional(CONF_LINK_DESCRIPTION, default=""): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    ),
                }
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing link subentry."""
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=user_input[CONF_LINK_NAME],
                data_updates=user_input,
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_LINK_NAME): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.TEXT)
                        ),
                        vol.Required(CONF_LINK_URL): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.URL)
                        ),
                        vol.Optional(CONF_LINK_DESCRIPTION, default=""): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.TEXT)
                        ),
                    }
                ),
                dict(subentry.data),
            ),
        )


class MembershipPlanSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding/editing membership plans."""

    _SCHEMA = vol.Schema(
        {
            vol.Required(CONF_PLAN_NAME): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(CONF_PLAN_VALUE): TextSelector(
                TextSelectorConfig(type=TextSelectorType.NUMBER)
            ),
            vol.Required(CONF_PLAN_CURRENCY): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(CONF_PLAN_BILLING_INTERVAL): SelectSelector(
                SelectSelectorConfig(options=BILLING_INTERVALS)
            ),
            vol.Optional(CONF_PLAN_DESCRIPTION, default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
        }
    )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new membership plan subentry."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_PLAN_NAME],
                data=user_input,
            )
        return self.async_show_form(step_id="user", data_schema=self._SCHEMA)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing membership plan subentry."""
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=user_input[CONF_PLAN_NAME],
                data_updates=user_input,
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                self._SCHEMA, dict(subentry.data)
            ),
        )


class LinkedSpaceSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding/editing linked spaces."""

    _SCHEMA = vol.Schema(
        {
            vol.Required(CONF_LINKED_SPACE_ENDPOINT): TextSelector(
                TextSelectorConfig(type=TextSelectorType.URL)
            ),
            vol.Optional(CONF_LINKED_SPACE_WEBSITE, default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.URL)
            ),
        }
    )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new linked space subentry."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_LINKED_SPACE_ENDPOINT],
                data=user_input,
            )
        return self.async_show_form(step_id="user", data_schema=self._SCHEMA)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing linked space subentry."""
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=user_input[CONF_LINKED_SPACE_ENDPOINT],
                data_updates=user_input,
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                self._SCHEMA, dict(subentry.data)
            ),
        )


class LocationAreaSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding/editing location areas."""

    _SCHEMA = vol.Schema(
        {
            vol.Required(CONF_AREA_NAME): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Optional(CONF_AREA_DESCRIPTION, default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Optional(CONF_AREA_SQUARE_METERS): vol.Coerce(float),
        }
    )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new location area subentry."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_AREA_NAME],
                data=user_input,
            )
        return self.async_show_form(step_id="user", data_schema=self._SCHEMA)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing location area subentry."""
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=user_input[CONF_AREA_NAME],
                data_updates=user_input,
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                self._SCHEMA, dict(subentry.data)
            ),
        )


class WindSensorSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding/editing a wind sensor station."""

    _SCHEMA = vol.Schema(
        {
            vol.Required(CONF_WIND_SPEED): EntitySelector(
                EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_WIND_GUST): EntitySelector(
                EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_WIND_DIRECTION): EntitySelector(
                EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_WIND_ELEVATION): EntitySelector(
                EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_WIND_NAME, default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Optional(CONF_WIND_LOCATION, default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
        }
    )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new wind sensor subentry."""
        if user_input is not None:
            title = user_input.get(CONF_WIND_NAME) or user_input[CONF_WIND_SPEED]
            return self.async_create_entry(title=title, data=user_input)
        return self.async_show_form(step_id="user", data_schema=self._SCHEMA)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing wind sensor subentry."""
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            title = user_input.get(CONF_WIND_NAME) or user_input[CONF_WIND_SPEED]
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=title,
                data_updates=user_input,
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                self._SCHEMA, dict(subentry.data)
            ),
        )
