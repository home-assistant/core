"""Support for the SpaceAPI."""

from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_LOCATION,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ADDRESS,
    CONF_EMAIL,
    CONF_ENTITY_ID,
    CONF_LOCATION,
    CONF_SENSORS,
    CONF_STATE,
    CONF_URL,
    STATE_ON,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.recorder import get_instance as get_recorder_instance
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_API_AREAS,
    ATTR_API_CAM,
    ATTR_API_CLOSED,
    ATTR_API_CONTACT,
    ATTR_API_EVENTS,
    ATTR_API_FEEDS,
    ATTR_API_LASTCHANGE,
    ATTR_API_LAT,
    ATTR_API_LINKED_SPACES,
    ATTR_API_LINKS,
    ATTR_API_LOGO,
    ATTR_API_LON,
    ATTR_API_MEMBERSHIP_PLANS,
    ATTR_API_NAME,
    ATTR_API_OPEN,
    ATTR_API_PROJECTS,
    ATTR_API_SENSOR_LOCATION,
    ATTR_API_SENSORS,
    ATTR_API_SPACE,
    ATTR_API_SPACEFED,
    ATTR_API_TIMESTAMP,
    ATTR_API_TYPE,
    ATTR_API_UNIT,
    ATTR_API_URL,
    ATTR_API_VALUE,
    ATTR_API_WIND,
    CONF_ACTIVITIES,
    CONF_AREA_DESCRIPTION,
    CONF_AREA_NAME,
    CONF_AREA_SQUARE_METERS,
    CONF_CAM,
    CONF_CONTACT,
    CONF_COUNTRY_CODE,
    CONF_DOOR_LOCKED,
    CONF_EVENTS_WINDOW_HOURS,
    CONF_FACEBOOK,
    CONF_FEED_BLOG,
    CONF_FEED_CALENDAR,
    CONF_FEED_FLICKR,
    CONF_FEED_TYPE,
    CONF_FEED_URL,
    CONF_FEED_WIKI,
    CONF_FEEDS,
    CONF_HINT,
    CONF_ICON_CLOSED,
    CONF_ICON_OPEN,
    CONF_ICONS,
    CONF_IRC,
    CONF_KEYMASTER_EMAIL,
    CONF_KEYMASTER_IRC_NICK,
    CONF_KEYMASTER_NAME,
    CONF_KEYMASTER_PHONE,
    CONF_KEYMASTER_TWITTER,
    CONF_KEYMASTERS,
    CONF_LINK_DESCRIPTION,
    CONF_LINK_NAME,
    CONF_LINK_URL,
    CONF_LINKED_SPACE_ENDPOINT,
    CONF_LINKED_SPACE_WEBSITE,
    CONF_LOGO,
    CONF_MESSAGE,
    CONF_ML,
    CONF_PHONE,
    CONF_PLAN_BILLING_INTERVAL,
    CONF_PLAN_CURRENCY,
    CONF_PLAN_DESCRIPTION,
    CONF_PLAN_NAME,
    CONF_PLAN_VALUE,
    CONF_PROJECTS,
    CONF_SIP,
    CONF_SPACE,
    CONF_SPACEFED,
    CONF_SPACENET,
    CONF_SPACESAML,
    CONF_TIMEZONE,
    CONF_TRIGGER_PERSON,
    CONF_TWITTER,
    CONF_WIND_DIRECTION,
    CONF_WIND_ELEVATION,
    CONF_WIND_GUST,
    CONF_WIND_LOCATION,
    CONF_WIND_NAME,
    CONF_WIND_SPEED,
    DOMAIN,
    SENSOR_DEFAULT_UNITS,
    SENSOR_REQUIRES_UNIT,
    SENSOR_TYPES,
    SPACEAPI_COMPATIBILITY,
    SUBENTRY_LINK,
    SUBENTRY_LINKED_SPACE,
    SUBENTRY_LOCATION_AREA,
    SUBENTRY_MEMBERSHIP_PLAN,
    SUBENTRY_WIND_SENSOR,
    URL_API_SPACEAPI,
)

type _SensorEntry = dict[str, str | bool | float | int]
type _WindField = dict[str, float | str]
type _WindEntry = dict[str, str | int | _WindField]
type _EventEntry = dict[str, str | int]

# ---------------------------------------------------------------------------
# Legacy YAML import validation (v13 → v15 migration, removed in 2026.12)
# All symbols in this block are used exclusively by CONFIG_SCHEMA below.
# ---------------------------------------------------------------------------

_CONF_CACHE = "cache"
_CONF_CACHE_SCHEDULE = "schedule"
_CONF_FOURSQUARE = "foursquare"
_CONF_IDENTICA = "identica"
_CONF_ISSUE_MAIL = "issue_mail"
_CONF_ISSUE_REPORT_CHANNELS = "issue_report_channels"
_CONF_JABBER = "jabber"
_CONF_M4 = "m4"
_CONF_MJPEG = "mjpeg"
_CONF_RADIO_SHOW = "radio_show"
_CONF_RADIO_SHOW_END = "end"
_CONF_RADIO_SHOW_NAME = "name"
_CONF_RADIO_SHOW_START = "start"
_CONF_RADIO_SHOW_TYPE = "type"
_CONF_RADIO_SHOW_URL = "url"
_CONF_SPACEPHONE = "spacephone"
_CONF_STREAM = "stream"
_CONF_USTREAM = "ustream"

LOCATION_SCHEMA = vol.Schema({vol.Optional(CONF_ADDRESS): cv.string})

SPACEFED_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SPACENET): cv.boolean,
        vol.Optional(CONF_SPACESAML): cv.boolean,
        vol.Optional(_CONF_SPACEPHONE): cv.boolean,  # Removed in v15
    }
)

FEED_SCHEMA = vol.Schema(
    {vol.Optional(CONF_FEED_TYPE): cv.string, vol.Required(CONF_FEED_URL): cv.url}
)

FEEDS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FEED_BLOG): FEED_SCHEMA,
        vol.Optional(CONF_FEED_WIKI): FEED_SCHEMA,
        vol.Optional(CONF_FEED_CALENDAR): FEED_SCHEMA,
        vol.Optional(CONF_FEED_FLICKR): FEED_SCHEMA,
    }
)

KEYMASTER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_KEYMASTER_NAME): cv.string,
        vol.Optional(CONF_KEYMASTER_IRC_NICK): cv.string,
        vol.Optional(CONF_KEYMASTER_PHONE): cv.string,
        vol.Optional(CONF_KEYMASTER_EMAIL): cv.string,
        vol.Optional(CONF_KEYMASTER_TWITTER): cv.string,
    }
)

CONTACT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_EMAIL): cv.string,
        vol.Optional(CONF_IRC): cv.string,
        vol.Optional(CONF_ML): cv.string,
        vol.Optional(CONF_PHONE): cv.string,
        vol.Optional(CONF_TWITTER): cv.string,
        vol.Optional(CONF_SIP): cv.string,
        vol.Optional(CONF_FACEBOOK): cv.string,
        vol.Optional(_CONF_IDENTICA): cv.string,  # Removed in v15
        vol.Optional(_CONF_FOURSQUARE): cv.string,  # Removed in v15
        vol.Optional(_CONF_JABBER): cv.string,  # Renamed to xmpp in v15
        vol.Optional(_CONF_ISSUE_MAIL): cv.string,  # Removed in v15
        vol.Optional(CONF_KEYMASTERS): vol.All(
            cv.ensure_list, [KEYMASTER_SCHEMA], vol.Length(min=1)
        ),
    }
)

STATE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Inclusive(CONF_ICON_CLOSED, CONF_ICONS): cv.url,
        vol.Inclusive(CONF_ICON_OPEN, CONF_ICONS): cv.url,
    }
)

SENSOR_SCHEMA = vol.Schema(
    {vol.In(SENSOR_TYPES): [cv.entity_id], cv.string: [cv.entity_id]}
)

STREAM_SCHEMA = vol.Schema(
    {
        vol.Optional(_CONF_M4): cv.url,
        vol.Optional(_CONF_MJPEG): cv.url,
        vol.Optional(_CONF_USTREAM): cv.url,
    }
)

CACHE_SCHEMA = vol.Schema(
    {
        vol.Required(_CONF_CACHE_SCHEDULE): cv.matches_regex(
            r"(m.02|m.05|m.10|m.15|m.30|h.01|h.02|h.04|h.08|h.12|d.01)"
        )
    }
)

RADIO_SHOW_SCHEMA = vol.Schema(
    {
        vol.Required(_CONF_RADIO_SHOW_NAME): cv.string,
        vol.Required(_CONF_RADIO_SHOW_URL): cv.url,
        vol.Required(_CONF_RADIO_SHOW_TYPE): cv.matches_regex(r"(mp3|ogg)"),
        vol.Required(_CONF_RADIO_SHOW_START): cv.string,
        vol.Required(_CONF_RADIO_SHOW_END): cv.string,
    }
)

# Accepts v13 YAML format for import migration to v15 config entries.
# Fields marked "Removed in v15" are dropped or converted during import.
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CONTACT): CONTACT_SCHEMA,
                vol.Required(_CONF_ISSUE_REPORT_CHANNELS): vol.All(  # Removed in v15
                    cv.ensure_list,
                    [vol.In([CONF_EMAIL, _CONF_ISSUE_MAIL, CONF_ML, CONF_TWITTER])],
                ),
                vol.Optional(CONF_LOCATION): LOCATION_SCHEMA,
                vol.Required(CONF_LOGO): cv.url,
                vol.Required(CONF_SPACE): cv.string,
                vol.Required(CONF_STATE): STATE_SCHEMA,
                vol.Required(CONF_URL): cv.string,
                vol.Optional(CONF_SENSORS): SENSOR_SCHEMA,
                vol.Optional(CONF_SPACEFED): SPACEFED_SCHEMA,
                vol.Optional(CONF_CAM): vol.All(
                    cv.ensure_list, [cv.url], vol.Length(min=1)
                ),
                vol.Optional(_CONF_STREAM): STREAM_SCHEMA,  # Removed in v15
                vol.Optional(CONF_FEEDS): FEEDS_SCHEMA,
                vol.Optional(_CONF_CACHE): CACHE_SCHEMA,  # Removed in v15
                vol.Optional(CONF_PROJECTS): vol.All(cv.ensure_list, [cv.url]),
                vol.Optional(_CONF_RADIO_SHOW): vol.All(  # Removed in v15
                    cv.ensure_list, [RADIO_SHOW_SCHEMA]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@dataclass
class SpaceAPIData:
    """Runtime data for the SpaceAPI integration."""

    config: dict[str, Any]


type SpaceAPIConfigEntry = ConfigEntry[SpaceAPIData]


def _merge_config(entry: SpaceAPIConfigEntry) -> dict[str, Any]:
    """Deep-merge entry.data and entry.options into a single config dict."""
    config: dict[str, Any] = dict(entry.data)
    for key, value in entry.options.items():
        if key in config and isinstance(config[key], dict) and isinstance(value, dict):
            config[key] = {**config[key], **value}
        else:
            config[key] = value
    return config


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up SpaceAPI from YAML config (import path)."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(_async_import_yaml(hass, config[DOMAIN]))
    return True


async def _async_import_yaml(hass: HomeAssistant, conf: dict[str, Any]) -> None:
    """Import YAML config and create deprecation issues."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=conf,
    )

    if result.get("type") is not FlowResultType.CREATE_ENTRY:
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2026.12.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "SpaceAPI",
        },
    )


async def async_setup_entry(hass: HomeAssistant, entry: SpaceAPIConfigEntry) -> bool:
    """Set up SpaceAPI from a config entry."""
    entry.runtime_data = SpaceAPIData(config=_merge_config(entry))
    hass.http.register_view(APISpaceApiView(entry.entry_id))
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SpaceAPIConfigEntry) -> bool:
    """Unload a SpaceAPI config entry."""
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: SpaceAPIConfigEntry
) -> None:
    """Handle options update."""
    entry.runtime_data = SpaceAPIData(config=_merge_config(entry))


class APISpaceApiView(HomeAssistantView):
    """View to provide details according to the SpaceAPI."""

    url = URL_API_SPACEAPI
    name = "api:spaceapi"

    def __init__(self, entry_id: str) -> None:
        """Initialize the SpaceAPI view."""
        self.requires_auth = False
        self.cors_allowed = True
        self._entry_id = entry_id

    @staticmethod
    def get_sensor_data(
        hass: HomeAssistant, sensor_type: str, entity_id: str
    ) -> _SensorEntry | None:
        """Get data from a sensor."""
        if not (sensor_state := hass.states.get(entity_id)):
            return None

        # door_locked must be boolean per v15 spec
        # lock entities: "locked" = True; binary_sensor entities: STATE_ON = True
        if sensor_type == CONF_DOOR_LOCKED:
            value: bool | float = sensor_state.state in (STATE_ON, "locked")
            sensor_data: _SensorEntry = {
                ATTR_NAME: sensor_state.name,
                ATTR_API_VALUE: value,
            }
        else:
            try:
                state = float(sensor_state.state)
            except ValueError:
                return None  # Skip sensors with non-numeric state

            sensor_data = {
                ATTR_NAME: sensor_state.name,
                ATTR_API_VALUE: state,
            }
            # Unit: use entity's unit if present, else type default, skip if none available but required
            unit: str | None = sensor_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            if unit is None:
                unit = SENSOR_DEFAULT_UNITS.get(sensor_type)
            if unit is not None:
                sensor_data[ATTR_API_UNIT] = unit
            elif sensor_type in SENSOR_REQUIRES_UNIT:
                return None  # Skip rather than emit invalid data

        if ATTR_API_SENSOR_LOCATION in sensor_state.attributes:
            sensor_data[ATTR_LOCATION] = sensor_state.attributes[
                ATTR_API_SENSOR_LOCATION
            ]

        sensor_data[ATTR_API_LASTCHANGE] = int(
            dt_util.as_timestamp(sensor_state.last_changed)
        )

        return sensor_data

    def _build_location(
        self,
        hass: HomeAssistant,
        spaceapi: dict[str, Any],
        entry: SpaceAPIConfigEntry,
    ) -> dict[str, Any]:
        """Build the location dict."""
        location: dict[str, Any] = {
            ATTR_API_LAT: round(hass.config.latitude, 6),
            ATTR_API_LON: round(hass.config.longitude, 6),
        }
        loc_opts: dict[str, str] = spaceapi.get(CONF_LOCATION) or {}
        for key in (CONF_ADDRESS, CONF_TIMEZONE, CONF_COUNTRY_CODE, CONF_HINT):
            if key in loc_opts:
                location[key] = loc_opts[key]
        areas = [
            {
                k: v
                for k, v in {
                    CONF_AREA_NAME: se.data[CONF_AREA_NAME],
                    CONF_AREA_DESCRIPTION: se.data.get(CONF_AREA_DESCRIPTION) or None,
                    CONF_AREA_SQUARE_METERS: se.data.get(CONF_AREA_SQUARE_METERS),
                }.items()
                if v is not None
            }
            for se in entry.subentries.values()
            if se.subentry_type == SUBENTRY_LOCATION_AREA
        ]
        if areas:
            location[ATTR_API_AREAS] = areas
        return location

    def _build_state(
        self,
        hass: HomeAssistant,
        spaceapi: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the state dict."""
        state_entity_id = spaceapi[CONF_STATE][ATTR_ENTITY_ID]
        state: dict[str, bool | int | float | str | dict[str, str]]
        space_state = hass.states.get(state_entity_id)
        if space_state is not None:
            entity_domain = state_entity_id.split(".", 1)[0]
            if entity_domain == "lock":
                is_open = space_state.state == "unlocked"
            elif entity_domain == "cover":
                is_open = space_state.state == "open"
            else:
                is_open = space_state.state == STATE_ON
            state = {
                ATTR_API_OPEN: is_open,
                ATTR_API_LASTCHANGE: int(
                    dt_util.as_timestamp(space_state.last_updated)
                ),
            }
        else:
            state = {ATTR_API_OPEN: False, ATTR_API_LASTCHANGE: 0}

        state_cfg = spaceapi.get(CONF_STATE, {})
        icons = {
            k: v
            for k, v in {
                ATTR_API_OPEN: state_cfg.get(CONF_ICON_OPEN),
                ATTR_API_CLOSED: state_cfg.get(CONF_ICON_CLOSED),
            }.items()
            if v
        }
        if icons:
            state[ATTR_ICON] = icons

        if message_entity_id := state_cfg.get(CONF_MESSAGE):
            if message_state := hass.states.get(message_entity_id):
                state[CONF_MESSAGE] = message_state.state

        if space_state is not None and (user_id := space_state.context.user_id):
            for person in hass.states.async_all("person"):
                if person.attributes.get("user_id") == user_id:
                    state[CONF_TRIGGER_PERSON] = person.name
                    break
        return state

    async def _build_events(
        self,
        hass: HomeAssistant,
        spaceapi: dict[str, Any],
    ) -> list[_EventEntry]:
        """Build events from activity entity history."""
        activity_ids: list[str] = spaceapi[CONF_ACTIVITIES]
        window_hours = spaceapi.get(CONF_EVENTS_WINDOW_HOURS)
        now = dt_util.now()
        start_time = now - timedelta(
            hours=int(window_hours) if window_hours is not None else 24
        )
        history = await get_recorder_instance(hass).async_add_executor_job(
            get_significant_states,
            hass,
            start_time,
            None,
            list(activity_ids),
            None,
            False,
            True,
        )
        events: list[_EventEntry] = []
        for entity_id, states in history.items():
            event_type = entity_id.split(".", 1)[1]
            live = hass.states.get(entity_id)
            entity_name = live.name if live else event_type.replace("_", " ")
            for state in states:
                if isinstance(state, dict) or state.state in ("unavailable", "unknown"):
                    continue
                events.append(
                    {
                        ATTR_API_NAME: entity_name,
                        ATTR_API_TYPE: event_type,
                        ATTR_API_TIMESTAMP: int(
                            dt_util.as_timestamp(state.last_changed)
                        ),
                    }
                )
        return events

    def _build_sensors(
        self,
        hass: HomeAssistant,
        spaceapi: dict[str, Any],
        entry: SpaceAPIConfigEntry,
    ) -> dict[str, list[_SensorEntry | _WindEntry]]:
        """Build sensors dict including wind subentries."""
        sensors: dict[str, list[str]] = spaceapi[CONF_SENSORS]
        sensors_data: dict[str, list[_SensorEntry | _WindEntry]] = {
            sensor_type: [
                sd
                for entity_id in entity_ids
                if (sd := self.get_sensor_data(hass, sensor_type, entity_id))
                is not None
            ]
            for sensor_type, entity_ids in sensors.items()
        }

        wind_sensors: list[_SensorEntry | _WindEntry] = []
        for se in entry.subentries.values():
            if se.subentry_type != SUBENTRY_WIND_SENSOR:
                continue
            wind_entry: _WindEntry = {}
            speed_state = None
            for field in (
                CONF_WIND_SPEED,
                CONF_WIND_GUST,
                CONF_WIND_DIRECTION,
                CONF_WIND_ELEVATION,
            ):
                if not (entity_id := se.data.get(field)):
                    continue
                if not (field_state := hass.states.get(entity_id)):
                    continue
                with suppress(ValueError):
                    wind_field: _WindField = {
                        ATTR_API_VALUE: float(field_state.state),
                        ATTR_API_UNIT: field_state.attributes.get(
                            ATTR_UNIT_OF_MEASUREMENT, ""
                        ),
                    }
                    wind_entry[field] = wind_field
                    if field == CONF_WIND_SPEED:
                        speed_state = field_state
            if CONF_WIND_SPEED not in wind_entry or speed_state is None:
                continue
            if name := se.data.get(CONF_WIND_NAME):
                wind_entry[ATTR_NAME] = name
            if loc := se.data.get(CONF_WIND_LOCATION):
                wind_entry[ATTR_LOCATION] = loc
            wind_entry[ATTR_API_LASTCHANGE] = int(
                dt_util.as_timestamp(speed_state.last_changed)
            )
            wind_sensors.append(wind_entry)
        if wind_sensors:
            sensors_data[ATTR_API_WIND] = wind_sensors
        return sensors_data

    async def get(self, request: web.Request) -> web.Response:
        """Get SpaceAPI data."""
        hass = request.app[KEY_HASS]

        entry = hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.json_message("Entry not found", 404)
        spaceapi: dict[str, Any] = entry.runtime_data.config

        data: dict[str, Any] = {
            "api_compatibility": SPACEAPI_COMPATIBILITY,
            ATTR_API_CONTACT: spaceapi.get(CONF_CONTACT, {}),
            ATTR_LOCATION: self._build_location(hass, spaceapi, entry),
            ATTR_API_LOGO: spaceapi[CONF_LOGO],
            ATTR_API_SPACE: spaceapi[CONF_SPACE],
            ATTR_API_URL: spaceapi[CONF_URL],
        }

        if CONF_STATE in spaceapi:
            data[ATTR_STATE] = self._build_state(hass, spaceapi)

        for attr, conf in (
            (ATTR_API_CAM, CONF_CAM),
            (ATTR_API_SPACEFED, CONF_SPACEFED),
            (ATTR_API_FEEDS, CONF_FEEDS),
            (ATTR_API_PROJECTS, CONF_PROJECTS),
        ):
            with suppress(KeyError):
                data[attr] = spaceapi[conf]

        if spaceapi.get(CONF_ACTIVITIES):
            data[ATTR_API_EVENTS] = await self._build_events(hass, spaceapi)

        links = [
            {
                k: v
                for k, v in {
                    CONF_LINK_NAME: se.data[CONF_LINK_NAME],
                    CONF_LINK_URL: se.data[CONF_LINK_URL],
                    CONF_LINK_DESCRIPTION: se.data.get(CONF_LINK_DESCRIPTION) or None,
                }.items()
                if v is not None
            }
            for se in entry.subentries.values()
            if se.subentry_type == SUBENTRY_LINK
        ]
        if links:
            data[ATTR_API_LINKS] = links

        membership_plans = [
            {
                k: v
                for k, v in {
                    CONF_PLAN_NAME: se.data[CONF_PLAN_NAME],
                    CONF_PLAN_VALUE: se.data[CONF_PLAN_VALUE],
                    CONF_PLAN_CURRENCY: se.data[CONF_PLAN_CURRENCY],
                    CONF_PLAN_BILLING_INTERVAL: se.data[CONF_PLAN_BILLING_INTERVAL],
                    CONF_PLAN_DESCRIPTION: se.data.get(CONF_PLAN_DESCRIPTION) or None,
                }.items()
                if v is not None
            }
            for se in entry.subentries.values()
            if se.subentry_type == SUBENTRY_MEMBERSHIP_PLAN
        ]
        if membership_plans:
            data[ATTR_API_MEMBERSHIP_PLANS] = membership_plans

        linked_spaces = [
            {
                k: v
                for k, v in {
                    CONF_LINKED_SPACE_ENDPOINT: se.data[CONF_LINKED_SPACE_ENDPOINT],
                    CONF_LINKED_SPACE_WEBSITE: se.data.get(CONF_LINKED_SPACE_WEBSITE)
                    or None,
                }.items()
                if v is not None
            }
            for se in entry.subentries.values()
            if se.subentry_type == SUBENTRY_LINKED_SPACE
        ]
        if linked_spaces:
            data[ATTR_API_LINKED_SPACES] = linked_spaces

        if isinstance(spaceapi.get(CONF_SENSORS), dict):
            data[ATTR_API_SENSORS] = self._build_sensors(hass, spaceapi, entry)

        return self.json(data)
