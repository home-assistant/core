"""Support for the SpaceAPI."""

from contextlib import suppress
from dataclasses import dataclass
import math
from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant import core as ha
from homeassistant.components.http import KEY_HASS, HomeAssistantView
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
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CAM,
    CONF_CONTACT,
    CONF_FACEBOOK,
    CONF_FEED_BLOG,
    CONF_FEED_CALENDAR,
    CONF_FEED_FLICKER,
    CONF_FEED_TYPE,
    CONF_FEED_URL,
    CONF_FEED_WIKI,
    CONF_FEEDS,
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
    CONF_LOGO,
    CONF_ML,
    CONF_PHONE,
    CONF_PROJECTS,
    CONF_SIP,
    CONF_SPACE,
    CONF_SPACEFED,
    CONF_SPACENET,
    CONF_SPACESAML,
    CONF_TWITTER,
    DATA_SPACEAPI,
    DOMAIN,
    SENSOR_TYPES,
    SPACEAPI_COMPATIBILITY,
    URL_API_SPACEAPI,
)

ATTR_ADDRESS = "address"
ATTR_SPACEFED = "spacefed"
ATTR_CAM = "cam"
ATTR_FEEDS = "feeds"
ATTR_PROJECTS = "projects"
ATTR_LAT = "lat"
ATTR_LON = "lon"
ATTR_CLOSED = "closed"
ATTR_CONTACT = "contact"
ATTR_LASTCHANGE = "lastchange"
ATTR_LOGO = "logo"
ATTR_OPEN = "open"
ATTR_SENSORS = "sensors"
ATTR_SPACE = "space"
ATTR_UNIT = "unit"
ATTR_URL = "url"
ATTR_VALUE = "value"
ATTR_SENSOR_LOCATION = "location"

LOCATION_SCHEMA = vol.Schema({vol.Optional(CONF_ADDRESS): cv.string})

SPACEFED_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SPACENET): cv.boolean,
        vol.Optional(CONF_SPACESAML): cv.boolean,
        vol.Optional("spacephone"): cv.boolean,
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
        vol.Optional(CONF_FEED_FLICKER): FEED_SCHEMA,
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
        vol.Optional("identica"): cv.string,
        vol.Optional("foursquare"): cv.string,
        vol.Optional("jabber"): cv.string,
        vol.Optional("issue_mail"): cv.string,
        vol.Optional(CONF_KEYMASTERS): vol.All(
            cv.ensure_list, [KEYMASTER_SCHEMA], vol.Length(min=1)
        ),
    },
    required=False,
)

STATE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Inclusive(CONF_ICON_CLOSED, CONF_ICONS): cv.url,
        vol.Inclusive(CONF_ICON_OPEN, CONF_ICONS): cv.url,
    },
    required=False,
)

SENSOR_SCHEMA = vol.Schema(
    {vol.In(SENSOR_TYPES): [cv.entity_id], cv.string: [cv.entity_id]}
)

STREAM_SCHEMA = vol.Schema(
    {
        vol.Optional("m4"): cv.url,
        vol.Optional("mjpeg"): cv.url,
        vol.Optional("ustream"): cv.url,
    }
)

CACHE_SCHEMA = vol.Schema(
    {
        vol.Required("schedule"): cv.matches_regex(
            r"(m.02|m.05|m.10|m.15|m.30|h.01|h.02|h.04|h.08|h.12|d.01)"
        )
    }
)

RADIO_SHOW_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required("url"): cv.url,
        vol.Required("type"): cv.matches_regex(r"(mp3|ogg)"),
        vol.Required("start"): cv.string,
        vol.Required("end"): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CONTACT): CONTACT_SCHEMA,
                vol.Required("issue_report_channels"): vol.All(
                    cv.ensure_list,
                    [vol.In([CONF_EMAIL, "issue_mail", CONF_ML, CONF_TWITTER])],
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
                vol.Optional("stream"): STREAM_SCHEMA,
                vol.Optional(CONF_FEEDS): FEEDS_SCHEMA,
                vol.Optional("cache"): CACHE_SCHEMA,
                vol.Optional(CONF_PROJECTS): vol.All(cv.ensure_list, [cv.url]),
                vol.Optional("radio_show"): vol.All(
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

    if result.get("type") is FlowResultType.ABORT and result.get("reason") not in (
        "already_configured",
        "single_instance_allowed",
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2026.12.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "SpaceAPI",
            },
        )
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

    def __init__(self, entry_id: str | None = None) -> None:
        """Initialize the SpaceAPI view."""
        self.requires_auth = False
        self.cors_allowed = True
        self._entry_id = entry_id

    @staticmethod
    def get_sensor_data(
        hass: HomeAssistant, spaceapi: dict[str, Any], entity_id: str
    ) -> dict[str, str | float | dict[str, str]] | None:
        """Get data from a sensor."""
        if not (sensor_state := hass.states.get(entity_id)):
            return None

        # SpaceAPI sensor values must be numbers
        try:
            state = float(sensor_state.state)
        except ValueError:
            state = math.nan
        sensor_data: dict[str, str | float | dict[str, str]] = {
            ATTR_NAME: sensor_state.name,
            ATTR_VALUE: state,
        }

        if ATTR_SENSOR_LOCATION in sensor_state.attributes:
            sensor_data[ATTR_LOCATION] = sensor_state.attributes[ATTR_SENSOR_LOCATION]
        else:
            sensor_data[ATTR_LOCATION] = spaceapi[CONF_SPACE]
        # Some sensors don't have a unit of measurement
        if ATTR_UNIT_OF_MEASUREMENT in sensor_state.attributes:
            sensor_data[ATTR_UNIT] = sensor_state.attributes[ATTR_UNIT_OF_MEASUREMENT]

        return sensor_data

    @ha.callback
    def get(self, request: web.Request) -> web.Response:
        """Get SpaceAPI data."""
        hass = request.app[KEY_HASS]

        if self._entry_id is not None:
            entry = hass.config_entries.async_get_entry(self._entry_id)
            if entry is None:
                return self.json_message("Entry not found", 404)
            spaceapi: dict[str, Any] = entry.runtime_data.config
        else:
            spaceapi = hass.data[DATA_SPACEAPI]

        location = {
            ATTR_LAT: hass.config.latitude,
            ATTR_LON: hass.config.longitude,
        }

        try:
            location[ATTR_ADDRESS] = spaceapi[ATTR_LOCATION][CONF_ADDRESS]
        except KeyError:
            pass
        except TypeError:
            pass

        data: dict[str, Any] = {
            "api_compatibility": SPACEAPI_COMPATIBILITY,
            ATTR_CONTACT: spaceapi[CONF_CONTACT],
            ATTR_LOCATION: location,
            ATTR_LOGO: spaceapi[CONF_LOGO],
            ATTR_SPACE: spaceapi[CONF_SPACE],
            ATTR_URL: spaceapi[CONF_URL],
        }

        if CONF_STATE in spaceapi:
            state_entity_id = spaceapi[CONF_STATE][ATTR_ENTITY_ID]

            state: dict[str, bool | int | float | str | dict[str, str]]
            if (space_state := hass.states.get(state_entity_id)) is not None:
                state = {
                    ATTR_OPEN: space_state.state != "off",
                    ATTR_LASTCHANGE: int(
                        dt_util.as_timestamp(space_state.last_updated)
                    ),
                }
            else:
                state = {
                    ATTR_OPEN: False,
                    ATTR_LASTCHANGE: 0,
                }

            with suppress(KeyError):
                state[ATTR_ICON] = {
                    ATTR_OPEN: spaceapi[CONF_STATE][CONF_ICON_OPEN],
                    ATTR_CLOSED: spaceapi[CONF_STATE][CONF_ICON_CLOSED],
                }

            data[ATTR_STATE] = state

        with suppress(KeyError):
            data[ATTR_CAM] = spaceapi[CONF_CAM]

        with suppress(KeyError):
            data[ATTR_SPACEFED] = spaceapi[CONF_SPACEFED]

        with suppress(KeyError):
            data[ATTR_FEEDS] = spaceapi[CONF_FEEDS]

        with suppress(KeyError):
            data[ATTR_PROJECTS] = spaceapi[CONF_PROJECTS]

        sensors: dict[str, list[str]] | None = spaceapi.get(CONF_SENSORS)
        if isinstance(sensors, dict):
            sensors_data: dict[str, list[dict[str, str | float | dict[str, str]]]] = {}
            for sensor_type, entity_ids in sensors.items():
                sensors_data[sensor_type] = [
                    sensor_data
                    for entity_id in entity_ids
                    if (sensor_data := self.get_sensor_data(hass, spaceapi, entity_id))
                    is not None
                ]
            data[ATTR_SENSORS] = sensors_data

        return self.json(data)
