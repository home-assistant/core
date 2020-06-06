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

MODEL_TITLE = "title"
MODEL_SWITCHES = "switches"

MODELS = {
    "shelly1": {MODEL_TITLE: "Shelly 1", MODEL_SWITCHES: 1},
    "shellyswitch": {MODEL_TITLE: "Shelly2", MODEL_SWITCHES: 2},
}
