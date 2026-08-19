"""Support for the SpaceAPI."""

from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_LOCATION,
    ATTR_NAME,
    ATTR_STATE,
    CONF_ADDRESS,
    CONF_COUNTRY_CODE,
    CONF_EMAIL,
    CONF_ENTITY_ID,
    CONF_LOCATION,
    CONF_SENSORS,
    CONF_STATE,
    CONF_URL,
    STATE_ON,
    EntityStateAttribute,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_API_CAM,
    ATTR_API_CLOSED,
    ATTR_API_CONTACT,
    ATTR_API_FEEDS,
    ATTR_API_LASTCHANGE,
    ATTR_API_LAT,
    ATTR_API_LOGO,
    ATTR_API_LON,
    ATTR_API_OPEN,
    ATTR_API_PROJECTS,
    ATTR_API_SENSOR_LOCATION,
    ATTR_API_SENSORS,
    ATTR_API_SPACE,
    ATTR_API_SPACEFED,
    ATTR_API_UNIT,
    ATTR_API_URL,
    ATTR_API_VALUE,
    CONF_CAM,
    CONF_CONTACT,
    CONF_DOOR_LOCKED,
    CONF_FACEBOOK,
    CONF_FEED_BLOG,
    CONF_FEED_CALENDAR,
    CONF_FEED_FLICKR,
    CONF_FEED_TYPE,
    CONF_FEED_URL,
    CONF_FEED_WIKI,
    CONF_FEEDS,
    CONF_FOURSQUARE,
    CONF_HINT,
    CONF_ICON_CLOSED,
    CONF_ICON_OPEN,
    CONF_ICONS,
    CONF_IDENTICA,
    CONF_IRC,
    CONF_ISSUE_MAIL,
    CONF_KEYMASTER_EMAIL,
    CONF_KEYMASTER_IRC_NICK,
    CONF_KEYMASTER_NAME,
    CONF_KEYMASTER_PHONE,
    CONF_KEYMASTER_TWITTER,
    CONF_KEYMASTERS,
    CONF_LOGO,
    CONF_MESSAGE,
    CONF_ML,
    CONF_PHONE,
    CONF_PROJECTS,
    CONF_SIP,
    CONF_SPACE,
    CONF_SPACEFED,
    CONF_SPACENET,
    CONF_SPACESAML,
    CONF_TIMEZONE,
    CONF_TRIGGER_PERSON,
    CONF_TWITTER,
    DOMAIN,
    SENSOR_DEFAULT_UNITS,
    SENSOR_TYPES,
    SPACEAPI_COMPATIBILITY,
    URL_API_SPACEAPI,
)

type _SensorEntry = dict[str, str | bool | float | int]

# ---------------------------------------------------------------------------
# Legacy YAML import validation (v13 → v15 migration, removed in 2026.12)
# All symbols in this block are used exclusively by CONFIG_SCHEMA below.
# ---------------------------------------------------------------------------

_CONF_CACHE = "cache"
_CONF_CACHE_SCHEDULE = "schedule"
_CONF_GOOGLE = "google"  # Removed in v15, dropped on import
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
        vol.Optional(CONF_IDENTICA): cv.string,
        vol.Optional(CONF_FOURSQUARE): cv.string,
        vol.Optional(_CONF_JABBER): cv.string,  # Renamed to xmpp in v15
        vol.Optional(CONF_ISSUE_MAIL): cv.string,
        vol.Optional(_CONF_GOOGLE): cv.string,  # Removed in v15, dropped on import
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
                    [vol.In([CONF_EMAIL, CONF_ISSUE_MAIL, CONF_ML, CONF_TWITTER])],
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
    """Merge entry.data and entry.options into a single config dict.

    Top-level keys present in both as dicts are merged one level deep, with
    option values overriding data values. Nested dicts beyond the first level
    and non-dict values are replaced, not merged recursively.
    """
    config: dict[str, Any] = dict(entry.data)
    for key, value in entry.options.items():
        if key in config and isinstance(config[key], dict) and isinstance(value, dict):
            config[key] = {**config[key], **value}
        else:
            config[key] = value
    return config


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up SpaceAPI."""
    # Register the view once for the lifetime of Home Assistant. Doing this in
    # async_setup_entry would re-register the same route on every entry reload
    # and raise on the duplicate URL.
    hass.http.register_view(APISpaceApiView())

    if DOMAIN in config:
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
    requires_auth = False
    cors_allowed = True

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
            # Unit: use the entity's unit if present, else fall back to the
            # type default. Types without a default simply omit the unit.
            unit: str | None = sensor_state.attributes.get(
                EntityStateAttribute.UNIT_OF_MEASUREMENT
            )
            if unit is None:
                unit = SENSOR_DEFAULT_UNITS.get(sensor_type)
            if unit is not None:
                sensor_data[ATTR_API_UNIT] = unit

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

    def _build_sensors(
        self,
        hass: HomeAssistant,
        spaceapi: dict[str, Any],
    ) -> dict[str, list[_SensorEntry]]:
        """Build the sensors dict.

        Sensor types that resolve to no values are omitted so the output never
        contains empty arrays.
        """
        sensors: dict[str, list[str]] = spaceapi.get(CONF_SENSORS, {})
        sensors_data: dict[str, list[_SensorEntry]] = {}
        for sensor_type, entity_ids in sensors.items():
            entries: list[_SensorEntry] = [
                sd
                for entity_id in entity_ids
                if (sd := self.get_sensor_data(hass, sensor_type, entity_id))
                is not None
            ]
            if entries:
                sensors_data[sensor_type] = entries

        return sensors_data

    async def get(self, request: web.Request) -> web.Response:
        """Get SpaceAPI data."""
        hass = request.app[KEY_HASS]

        # single_config_entry integration: there is at most one loaded entry.
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            return self.json_message("SpaceAPI not configured", 404)
        entry = entries[0]
        spaceapi: dict[str, Any] = entry.runtime_data.config

        contact = spaceapi.get(CONF_CONTACT, {})

        data: dict[str, Any] = {
            "api_compatibility": SPACEAPI_COMPATIBILITY,
            ATTR_API_CONTACT: contact,
            ATTR_LOCATION: self._build_location(hass, spaceapi),
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

        if sensors := self._build_sensors(hass, spaceapi):
            data[ATTR_API_SENSORS] = sensors

        return self.json(data)
