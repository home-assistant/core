"""Constants for the Alexa integration."""
from collections import OrderedDict

from homeassistant.components.climate import const as climate
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT

DOMAIN = "alexa"
EVENT_ALEXA_SMART_HOME = "alexa_smart_home"

# Flash briefing constants
CONF_UID = "uid"
CONF_TITLE = "title"
CONF_AUDIO = "audio"
CONF_TEXT = "text"
CONF_DISPLAY_URL = "display_url"

CONF_FILTER = "filter"
CONF_ENTITY_CONFIG = "entity_config"
CONF_ENDPOINT = "endpoint"
CONF_LOCALE = "locale"

ATTR_UID = "uid"
ATTR_UPDATE_DATE = "updateDate"
ATTR_TITLE_TEXT = "titleText"
ATTR_STREAM_URL = "streamUrl"
ATTR_MAIN_TEXT = "mainText"
ATTR_REDIRECTION_URL = "redirectionURL"

SYN_RESOLUTION_MATCH = "ER_SUCCESS_MATCH"

# Alexa requires timestamps to be formatted according to ISO 8601, YYYY-MM-DDThh:mm:ssZ
# https://developer.amazon.com/es-ES/docs/alexa/device-apis/alexa-scenecontroller.html#activate-response-event
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

API_DIRECTIVE = "directive"
API_ENDPOINT = "endpoint"
API_EVENT = "event"
API_CONTEXT = "context"
API_HEADER = "header"
API_PAYLOAD = "payload"
API_SCOPE = "scope"
API_CHANGE = "change"
API_PASSWORD = "password"

CONF_DISPLAY_CATEGORIES = "display_categories"
CONF_SUPPORTED_LOCALES = (
    "de-DE",
    "en-AU",
    "en-CA",
    "en-GB",
    "en-IN",
    "en-US",
    "es-ES",
    "es-MX",
    "es-US",
    "fr-CA",
    "fr-FR",
    "hi-IN",
    "it-IT",
    "ja-JP",
    "pt-BR",
)

API_TEMP_UNITS = {TEMP_FAHRENHEIT: "FAHRENHEIT", TEMP_CELSIUS: "CELSIUS"}

# Needs to be ordered dict for `async_api_set_thermostat_mode` which does a
# reverse mapping of this dict and we want to map the first occurrence of OFF
# back to HA state.
API_THERMOSTAT_MODES = OrderedDict(
    [
        (climate.HVAC_MODE_HEAT, "HEAT"),
        (climate.HVAC_MODE_COOL, "COOL"),
        (climate.HVAC_MODE_HEAT_COOL, "AUTO"),
        (climate.HVAC_MODE_AUTO, "AUTO"),
        (climate.HVAC_MODE_OFF, "OFF"),
        (climate.HVAC_MODE_FAN_ONLY, "OFF"),
        (climate.HVAC_MODE_DRY, "CUSTOM"),
    ]
)
API_THERMOSTAT_MODES_CUSTOM = {climate.HVAC_MODE_DRY: "DEHUMIDIFY"}
API_THERMOSTAT_PRESETS = {climate.PRESET_ECO: "ECO"}

# AlexaModeController does not like a single mode for the fan preset, we add PRESET_MODE_NA if a fan has only one preset_mode
PRESET_MODE_NA = "-"


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


class Inputs:
    """Valid names for the InputController.

    https://developer.amazon.com/docs/device-apis/alexa-property-schemas.html#input
    """

    VALID_SOURCE_NAME_MAP = {
        "antenna": "TUNER",
        "antennatv": "TUNER",
        "aux": "AUX 1",
        "aux1": "AUX 1",
        "aux2": "AUX 2",
        "aux3": "AUX 3",
        "aux4": "AUX 4",
        "aux5": "AUX 5",
        "aux6": "AUX 6",
        "aux7": "AUX 7",
        "bluray": "BLURAY",
        "blurayplayer": "BLURAY",
        "cable": "CABLE",
        "cd": "CD",
        "coax": "COAX 1",
        "coax1": "COAX 1",
        "coax2": "COAX 2",
        "composite": "COMPOSITE 1",
        "composite1": "COMPOSITE 1",
        "dvd": "DVD",
        "game": "GAME",
        "gameconsole": "GAME",
        "hdradio": "HD RADIO",
        "hdmi": "HDMI 1",
        "hdmi1": "HDMI 1",
        "hdmi2": "HDMI 2",
        "hdmi3": "HDMI 3",
        "hdmi4": "HDMI 4",
        "hdmi5": "HDMI 5",
        "hdmi6": "HDMI 6",
        "hdmi7": "HDMI 7",
        "hdmi8": "HDMI 8",
        "hdmi9": "HDMI 9",
        "hdmi10": "HDMI 10",
        "hdmiarc": "HDMI ARC",
        "input": "INPUT 1",
        "input1": "INPUT 1",
        "input2": "INPUT 2",
        "input3": "INPUT 3",
        "input4": "INPUT 4",
        "input5": "INPUT 5",
        "input6": "INPUT 6",
        "input7": "INPUT 7",
        "input8": "INPUT 8",
        "input9": "INPUT 9",
        "input10": "INPUT 10",
        "ipod": "IPOD",
        "line": "LINE 1",
        "line1": "LINE 1",
        "line2": "LINE 2",
        "line3": "LINE 3",
        "line4": "LINE 4",
        "line5": "LINE 5",
        "line6": "LINE 6",
        "line7": "LINE 7",
        "mediaplayer": "MEDIA PLAYER",
        "optical": "OPTICAL 1",
        "optical1": "OPTICAL 1",
        "optical2": "OPTICAL 2",
        "phono": "PHONO",
        "playstation": "PLAYSTATION",
        "playstation3": "PLAYSTATION 3",
        "playstation4": "PLAYSTATION 4",
        "rokumediaplayer": "MEDIA PLAYER",
        "satellite": "SATELLITE",
        "satellitetv": "SATELLITE",
        "smartcast": "SMARTCAST",
        "tuner": "TUNER",
        "tv": "TV",
        "usbdac": "USB DAC",
        "video": "VIDEO 1",
        "video1": "VIDEO 1",
        "video2": "VIDEO 2",
        "video3": "VIDEO 3",
        "xbox": "XBOX",
    }

    VALID_SOUND_MODE_MAP = {
        "movie": "MOVIE",
        "music": "MUSIC",
        "night": "NIGHT",
        "sport": "SPORT",
        "tv": "TV",
    }
