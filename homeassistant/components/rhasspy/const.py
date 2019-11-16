"""Constants for Rhasspy integration.

For more details about this integration, please refer to the documentation at
https://home-assistant.io/integrations/rhasspy/
"""
DOMAIN = "rhasspy"

# Language-specific profiles available for Rhasspy.
# See https://github.com/synesthesiam/rhasspy-profiles/releases
SUPPORT_LANGUAGES = [
    "en-US",
    "nl-NL",
    "fr-FR",
    "de-DE",
    "el-GR",
    "it-IT",
    "pt-BR",
    "ru-RU",
    "es-ES",
    "sv-SV",
    "vi-VI",
]

# -----------------------------------------------------------------------------
# Rhasspy Intents
# -----------------------------------------------------------------------------

# Confirms or disconfirms if a device is currently on
INTENT_IS_DEVICE_ON = "IsDeviceOn"

# Confirms or disconfirms if a device is currently off
INTENT_IS_DEVICE_OFF = "IsDeviceOff"

# Confirms or disconfirms if a cover is currently open
INTENT_IS_COVER_OPEN = "IsCoverOpen"

# Confirms or disconfirms if a cover is currently closed
INTENT_IS_COVER_CLOSED = "IsCoverClosed"

# Confirms or disconfirms the state of a device
INTENT_IS_DEVICE_STATE = "IsDeviceState"

# Reports a device's state
INTENT_DEVICE_STATE = "DeviceState"

# Runs an automation by name now
INTENT_TRIGGER_AUTOMATION = "TriggerAutomation"

# Runs an automation by name after a delay
INTENT_TRIGGER_AUTOMATION_LATER = "TriggerAutomationLater"

# Sets a timer
INTENT_SET_TIMER = "SetTimer"

# Fired when SetTimer timer elapses
INTENT_TIMER_READY = "TimerReady"

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Base URL of Rhasspy web API
CONF_API_URL = "api_url"

# Language to use for generating default utterances
CONF_LANGUAGE = "language"

# User defined commands by intent
CONF_INTENT_COMMANDS = "intent_commands"

# User defined slots and values
CONF_SLOTS = "slots"

# User defined words and pronunciations
CONF_CUSTOM_WORDS = "custom_words"

# Name replacements for entities
CONF_NAME_REPLACE = "name_replace"

# If True, Rhasspy conversation agent is registered
CONF_REGISTER_CONVERSATION = "register_conversation"

# List of intents for Rhasspy to handle
CONF_HANDLE_INTENTS = "handle_intents"

# Speech responses for intent handling
CONF_RESPONSE_TEMPLATES = "reponse_templates"

# State names for question intents (e.g., "on" for INTENT_IS_DEVICE_ON)
CONF_INTENT_STATES = "intent_states"

# Entities/domains to include/exclude for auto-generated commands
CONF_INTENT_FILTERS = "intent_filters"

# Seconds before re-training occurs after new component loaded
CONF_TRAIN_TIMEOUT = "train_timeout"

# List of possible items that can be added to the shopping list
CONF_SHOPPING_LIST_ITEMS = "shopping_list_items"

# If True, generate default voice commands
CONF_MAKE_INTENT_COMMANDS = "make_intent_commands"

# Configuration keys
KEY_COMMAND = "command"
KEY_COMMANDS = "commands"
KEY_COMMAND_TEMPLATE = "command_template"
KEY_COMMAND_TEMPLATES = "command_templates"
KEY_DATA = "data"
KEY_DATA_TEMPLATE = "data_template"
KEY_INCLUDE = "include"
KEY_EXCLUDE = "exclude"
KEY_DOMAINS = "domains"
KEY_ENTITIES = "entities"
KEY_REGEX = "regex"

# -----------------------------------------------------------------------------
# Services
# -----------------------------------------------------------------------------

SERVICE_TRAIN = "train"
EVENT_RHASSPY_TRAINED = "rhasspy_trained"
