"""Constants for the spokestack integration."""
DOMAIN = "spokestack"

CONF_IDENTITY = "identity"
CONF_SECRET_KEY = "secret_key"

SUPPORTED_LANGUAGES = ["en-US"]
SUPPORTED_MODES = ["markdown", "ssml", "text"]
SUPPORTED_OPTIONS = ["voice", "mode", "profile"]

DEFAULT_IDENTITY = " "
DEFAULT_SECRET_KEY = " "
DEFAULT_VOICE = "demo-male"
DEFAULT_LANG = "en-US"
DEFAULT_MODE = "text"
DEFAULT_PROFILE = "default"

PLATFORMS = ["tts"]
