"""constants."""

import datetime
import logging

from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.helpers import llm

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
)
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.group.const import DOMAIN as GROUP_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor.const import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN

VERSION = "1.1.25"
NAME = "EffortlessHome"
name_internal = "effortlesshome"
DOMAIN = "effortlesshome"

# Labels we want to ensure exist
LABELS = [
    "Favorite",
    "NotForSecurityMonitoring",
]

# Configuration and options
CONF_ENABLED = "enabled"
CONF_USERNAME = "username"
CONF_SYSTEMID = "systemid"

CUSTOM_COMPONENTS = "custom_components"
INTEGRATION_FOLDER = DOMAIN

PRESENCE_LOCK_SWITCH_PREFIX = ""
PRESENCE_LOCK_SWITCH_ENTITY_PREFIX = "switch.area_presence_lock_"

SLEEP_MODE_SWITCH_PREFIX = "Sleep Mode "
SLEEP_MODE_SWITCH_ENTITY_PREFIX = "switch.area_sleep_mode_"

PRESENCE_BINARY_SENSOR_PREFIX = ""
PRESENCE_BINARY_SENSOR_ENTITY_PREFIX = "binary_sensor.area_presence_"

ILLUMINANCE_SENSOR_PREFIX = ""
ILLUMINANCE_SENSOR_ENTITY_PREFIX = "sensor.area_illuminance_"

TEMPERATURE_SENSOR_PREFIX = ""
TEMPERATURE_SENSOR_ENTITY_PREFIX = "sensor.area_temperature_"

HUMIDITY_SENSOR_PREFIX = ""
HUMIDITY_SENSOR_ENTITY_PREFIX = "sensor.area_humidity_"

COVER_GROUP_PREFIX = ""
COVER_GROUP_ENTITY_PREFIX = "cover.area_covers_"

LIGHT_GROUP_PREFIX = ""
LIGHT_GROUP_ENTITY_PREFIX = "light.area_"

INITIALIZATION_TIME = datetime.timedelta(seconds=60)
SENSOR_ARM_TIME = datetime.timedelta(seconds=5)

ALARM_TYPE_MED_ALERT = "medicalalert"
ALARM_TYPE_SECURITY = "security"
ALARM_TYPE_MONITORING = "monitoring"

COMMAND_ARM_NIGHT = "arm_night"
COMMAND_ARM_AWAY = "arm_away"
COMMAND_ARM_HOME = "arm_home"
COMMAND_ARM_CUSTOM_BYPASS = "arm_custom_bypass"
COMMAND_ARM_VACATION = "arm_vacation"
COMMAND_DISARM = "disarm"

COMMANDS = [
    COMMAND_DISARM,
    COMMAND_ARM_AWAY,
    COMMAND_ARM_NIGHT,
    COMMAND_ARM_HOME,
    COMMAND_ARM_CUSTOM_BYPASS,
    COMMAND_ARM_VACATION,
]

EVENT_DISARM = "disarm"
EVENT_LEAVE = "leave"
EVENT_ARM = "arm"
EVENT_ENTRY = "entry"
EVENT_TRIGGER = "trigger"
EVENT_FAILED_TO_ARM = "failed_to_arm"
EVENT_COMMAND_NOT_ALLOWED = "command_not_allowed"
EVENT_INVALID_CODE_PROVIDED = "invalid_code_provided"
EVENT_NO_CODE_PROVIDED = "no_code_provided"
EVENT_TRIGGER_TIME_EXPIRED = "trigger_time_expired"
EVENT_READY_TO_ARM_MODES_CHANGED = "ready_to_arm_modes_changed"

ISSUE_TYPE_INVALID_AREA = "invalid_area_config"

# Fetch entities from these domains:
RELEVANT_DOMAINS = [
    BINARY_SENSOR_DOMAIN,
    SENSOR_DOMAIN,
    SWITCH_DOMAIN,
    LIGHT_DOMAIN,
    COVER_DOMAIN,
]

"""Constants for the Google Translate text-to-speech integration."""

CONF_TLD = "tld"
DEFAULT_LANG = "en"
DEFAULT_TLD = "com"

# INSTRUCTIONS TO UPDATE LIST:
#
# Removal:
# Removal is as simple as deleting the line containing the language code no longer
# supported.
#
# Addition:
# In order to add to this list, follow the below steps:
# 1. Find out if the language is supported: Go to Google Translate website and try
#    translating any word from English into your desired language.
#    If the "speech" icon is grayed out or no speech is generated, the language is
#    not supported and cannot be added. Otherwise, proceed:
# 2. Grab the language code from https://cloud.google.com/translate/docs/languages
# 3. Add the language code in SUPPORT_LANGUAGES, making sure to not disturb the
#    alphabetical nature of the list.

SUPPORT_LANGUAGES = [
    "af",
    "am",
    "ar",
    "bg",
    "bn",
    "bs",
    "ca",
    "cs",
    "cy",
    "da",
    "de",
    "el",
    "en",
    "es",
    "et",
    "eu",
    "fi",
    "fil",
    "fr",
    "gl",
    "gu",
    "ha",
    "hi",
    "hr",
    "hu",
    "id",
    "is",
    "it",
    "iw",
    "ja",
    "jw",
    "km",
    "kn",
    "ko",
    "la",
    "lt",
    "lv",
    "ml",
    "mr",
    "ms",
    "my",
    "ne",
    "nl",
    "no",
    "pa",
    "pl",
    "pt",
    "ro",
    "ru",
    "si",
    "sk",
    "sq",
    "sr",
    "su",
    "sv",
    "sw",
    "ta",
    "te",  # codespell:ignore te
    "th",
    "tl",
    "tr",
    "uk",
    "ur",
    "vi",
    # dialects
    "zh-CN",
    "zh-cn",
    "zh-tw",
    "en-us",
    "en-ca",
    "en-uk",
    "en-gb",
    "en-au",
    "en-gh",
    "en-in",
    "en-ie",
    "en-nz",
    "en-ng",
    "en-ph",
    "en-za",
    "en-tz",
    "fr-ca",
    "fr-fr",
    "pt-br",
    "pt-pt",
    "es-es",
    "es-us",
]

SUPPORT_TLD = [
    "com",
    "ad",
    "ae",
    "com.af",
    "com.ag",
    "com.ai",
    "al",
    "am",
    "co.ao",
    "com.ar",
    "as",
    "at",
    "com.au",
    "az",
    "ba",
    "com.bd",
    "be",
    "bf",
    "bg",
    "com.bh",
    "bi",
    "bj",
    "com.bn",
    "com.bo",
    "com.br",
    "bs",
    "bt",
    "co.bw",
    "by",
    "com.bz",
    "ca",
    "cd",
    "cf",
    "cg",
    "ch",
    "ci",
    "co.ck",
    "cl",
    "cm",
    "cn",
    "com.co",
    "co.cr",
    "com.cu",
    "cv",
    "com.cy",
    "cz",
    "de",
    "dj",
    "dk",
    "dm",
    "com.do",
    "dz",
    "com.ec",
    "ee",
    "com.eg",
    "es",
    "com.et",
    "fi",
    "com.fj",
    "fm",
    "fr",
    "ga",
    "ge",
    "gg",
    "com.gh",
    "com.gi",
    "gl",
    "gm",
    "gr",
    "com.gt",
    "gy",
    "com.hk",
    "hn",
    "hr",
    "ht",
    "hu",
    "co.id",
    "ie",
    "co.il",
    "im",
    "co.in",
    "iq",
    "is",
    "it",
    "je",
    "com.jm",
    "jo",
    "co.jp",
    "co.ke",
    "com.kh",
    "ki",
    "kg",
    "co.kr",
    "com.kw",
    "kz",
    "la",
    "com.lb",
    "li",
    "lk",
    "co.ls",
    "lt",
    "lu",
    "lv",
    "com.ly",
    "co.ma",
    "md",
    "me",
    "mg",
    "mk",
    "ml",
    "com.mm",
    "mn",
    "ms",
    "com.mt",
    "mu",
    "mv",
    "mw",
    "com.mx",
    "com.my",
    "co.mz",
    "com.na",
    "com.ng",
    "com.ni",
    "ne",
    "nl",
    "no",
    "com.np",
    "nr",
    "nu",
    "co.nz",
    "com.om",
    "com.pa",
    "com.pe",
    "com.pg",
    "com.ph",
    "com.pk",
    "pl",
    "pn",
    "com.pr",
    "ps",
    "pt",
    "com.py",
    "com.qa",
    "ro",
    "ru",
    "rw",
    "com.sa",
    "com.sb",
    "sc",
    "se",
    "com.sg",
    "sh",
    "si",
    "sk",
    "com.sl",
    "sn",
    "so",
    "sm",
    "sr",
    "st",
    "com.sv",
    "td",
    "tg",
    "co.th",
    "com.tj",
    "tl",
    "tm",
    "tn",
    "to",
    "com.tr",
    "tt",
    "com.tw",
    "co.tz",
    "com.ua",
    "co.ug",
    "co.uk",
    "com.uy",
    "co.uz",
    "com.vc",
    "co.ve",
    "vg",
    "co.vi",
    "com.vn",
    "vu",
    "ws",
    "rs",
    "co.za",
    "co.zm",
    "co.zw",
    "cat",
]


@dataclass
class Dialect:
    """Language and TLD for a dialect supported by Google Translate."""

    lang: str
    tld: str


MAP_LANG_TLD: dict[str, Dialect] = {
    "en-us": Dialect("en", "com"),
    "en-gb": Dialect("en", "co.uk"),
    "en-uk": Dialect("en", "co.uk"),
    "en-au": Dialect("en", "com.au"),
    "en-ca": Dialect("en", "ca"),
    "en-in": Dialect("en", "co.in"),
    "en-ie": Dialect("en", "ie"),
    "en-za": Dialect("en", "co.za"),
    "fr-ca": Dialect("fr", "ca"),
    "fr-fr": Dialect("fr", "fr"),
    "pt-br": Dialect("pt", "com.br"),
    "pt-pt": Dialect("pt", "pt"),
    "es-es": Dialect("es", "es"),
    "es-us": Dialect("es", "com"),
}


"""Constants for the Google Generative AI Conversation integration."""

CONF_PROMPT = "prompt"
DEFAULT_STT_PROMPT = "Transcribe the attached audio"

CONF_RECOMMENDED = "recommended"
CONF_CHAT_MODEL = "chat_model"
RECOMMENDED_CHAT_MODEL = "models/gemini-2.5-flash"
RECOMMENDED_TTS_MODEL = "models/gemini-2.5-flash-preview-tts"
RECOMMENDED_IMAGE_MODEL = "models/gemini-2.5-flash-image-preview"
CONF_TEMPERATURE = "temperature"
RECOMMENDED_TEMPERATURE = 1.0
CONF_TOP_P = "top_p"
RECOMMENDED_TOP_P = 0.95
CONF_TOP_K = "top_k"
RECOMMENDED_TOP_K = 64
CONF_MAX_TOKENS = "max_tokens"
RECOMMENDED_MAX_TOKENS = 3000
CONF_HARASSMENT_BLOCK_THRESHOLD = "harassment_block_threshold"
CONF_HATE_BLOCK_THRESHOLD = "hate_block_threshold"
CONF_SEXUAL_BLOCK_THRESHOLD = "sexual_block_threshold"
CONF_DANGEROUS_BLOCK_THRESHOLD = "dangerous_block_threshold"
RECOMMENDED_HARM_BLOCK_THRESHOLD = "BLOCK_MEDIUM_AND_ABOVE"
CONF_USE_GOOGLE_SEARCH_TOOL = "enable_google_search_tool"
RECOMMENDED_USE_GOOGLE_SEARCH_TOOL = False

TIMEOUT_MILLIS = 10000
FILE_POLLING_INTERVAL_SECONDS = 0.05

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_RECOMMENDED: True,
}

RECOMMENDED_STT_OPTIONS = {
    CONF_PROMPT: DEFAULT_STT_PROMPT,
    CONF_RECOMMENDED: True,
}

RECOMMENDED_TTS_OPTIONS = {
    CONF_RECOMMENDED: True,
}

RECOMMENDED_AI_TASK_OPTIONS = {
    CONF_RECOMMENDED: True,
}


ATTR_LATITUDE = "latitude"
ATTR_LONGITUDE = "longitude"
CONF_EMAIL = "email"
CONF_TRACKING_ENABLED = "tracking_enabled"
CONF_NOTIFICATIONS_ENABLED = "notifications_enabled"
WEBHOOK_UPDATE_PUSH_TOKEN = "effortlesshome_push_token"