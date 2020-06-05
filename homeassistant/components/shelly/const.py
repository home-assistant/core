"""Constants for the Shelly integration."""

DOMAIN = "shelly"

ANNOUNCE_COMMAND = "announce"
UPDATE_COMMAND = "update"
COMMAND_SUFFIX = "command"
COMMON_ANNOUNCE_TOPIC = "shellies/announce"
COMMON_COMMAND_TOPIC = f"shellies/{COMMAND_SUFFIX}"

CONF_ID = "id"
CONF_MODEL = "model"
CONF_TOPIC = "topic"

MODELS = {"shelly1": {"title": "Shelly 1"}}
