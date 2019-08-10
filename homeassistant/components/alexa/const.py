"""Constants for the Alexa integration."""
from collections import OrderedDict

from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.components.climate import const as climate
from homeassistant.components import fan


DOMAIN = "alexa"

# Flash briefing constants
CONF_UID = "uid"
CONF_TITLE = "title"
CONF_AUDIO = "audio"
CONF_TEXT = "text"
CONF_DISPLAY_URL = "display_url"

CONF_FILTER = "filter"
CONF_ENTITY_CONFIG = "entity_config"
CONF_ENDPOINT = "endpoint"
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"

ATTR_UID = "uid"
ATTR_UPDATE_DATE = "updateDate"
ATTR_TITLE_TEXT = "titleText"
ATTR_STREAM_URL = "streamUrl"
ATTR_MAIN_TEXT = "mainText"
ATTR_REDIRECTION_URL = "redirectionURL"

SYN_RESOLUTION_MATCH = "ER_SUCCESS_MATCH"

DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.0Z"

API_DIRECTIVE = "directive"
API_ENDPOINT = "endpoint"
API_EVENT = "event"
API_CONTEXT = "context"
API_HEADER = "header"
API_PAYLOAD = "payload"
API_SCOPE = "scope"
API_CHANGE = "change"

CONF_DESCRIPTION = "description"
CONF_DISPLAY_CATEGORIES = "display_categories"

API_TEMP_UNITS = {TEMP_FAHRENHEIT: "FAHRENHEIT", TEMP_CELSIUS: "CELSIUS"}

# Needs to be ordered dict for `async_api_set_thermostat_mode` which does a
# reverse mapping of this dict and we want to map the first occurrance of OFF
# back to HA state.
API_THERMOSTAT_MODES = OrderedDict(
    [
        (climate.HVAC_MODE_HEAT, "HEAT"),
        (climate.HVAC_MODE_COOL, "COOL"),
        (climate.HVAC_MODE_HEAT_COOL, "AUTO"),
        (climate.HVAC_MODE_AUTO, "AUTO"),
        (climate.HVAC_MODE_OFF, "OFF"),
        (climate.HVAC_MODE_FAN_ONLY, "OFF"),
        (climate.HVAC_MODE_DRY, "OFF"),
    ]
)
API_THERMOSTAT_PRESETS = {climate.PRESET_ECO: "ECO"}

PERCENTAGE_FAN_MAP = {fan.SPEED_LOW: 33, fan.SPEED_MEDIUM: 66, fan.SPEED_HIGH: 100}


class Cause:
    """Possible causes for property changes.

    https://developer.amazon.com/docs/smarthome/state-reporting-for-a-smart-home-skill.html#cause-object
    """

    # Indicates that the event was caused by a customer interaction with an
    # application. For example, a customer switches on a light, or locks a door
    # using the Alexa app or an app provided by a device vendor.
    APP_INTERACTION = "APP_INTERACTION"

    # Indicates that the event was caused by a physical interaction with an
    # endpoint. For example manually switching on a light or manually locking a
    # door lock
    PHYSICAL_INTERACTION = "PHYSICAL_INTERACTION"

    # Indicates that the event was caused by the periodic poll of an appliance,
    # which found a change in value. For example, you might poll a temperature
    # sensor every hour, and send the updated temperature to Alexa.
    PERIODIC_POLL = "PERIODIC_POLL"

    # Indicates that the event was caused by the application of a device rule.
    # For example, a customer configures a rule to switch on a light if a
    # motion sensor detects motion. In this case, Alexa receives an event from
    # the motion sensor, and another event from the light to indicate that its
    # state change was caused by the rule.
    RULE_TRIGGER = "RULE_TRIGGER"

    # Indicates that the event was caused by a voice interaction with Alexa.
    # For example a user speaking to their Echo device.
    VOICE_INTERACTION = "VOICE_INTERACTION"
