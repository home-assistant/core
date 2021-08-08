"""Constants for the spokestack integration."""
DOMAIN = "spokestack"

CONF_KEY_ID = "key_id"
CONF_KEY_SECRET = "key_secret"
CONF_MODE = "mode"
CONF_VOICE = "voice"
CONF_LANG = "lang"
CONF_PROFILE = "profile"

SUPPORTED_LANGUAGES = ["en-US"]
SUPPORTED_MODES = ["markdown", "ssml", "text"]
SUPPORTED_OPTIONS = ["voice", "mode", "profile"]

DEFAULT_VOICE = "demo-male"
DEFAULT_LANG = "en-US"
DEFAULT_MODE = "text"
DEFAULT_PROFILE = "default"
