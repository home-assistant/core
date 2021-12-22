"""Constants for the cloud component."""
DOMAIN = "cloud"
REQUEST_TIMEOUT = 10

PREF_ENABLE_ALEXA = "alexa_enabled"
PREF_ENABLE_GOOGLE = "google_enabled"
PREF_ENABLE_REMOTE = "remote_enabled"
PREF_GOOGLE_SECURE_DEVICES_PIN = "google_secure_devices_pin"
PREF_CLOUDHOOKS = "cloudhooks"
PREF_CLOUD_USER = "cloud_user"
PREF_GOOGLE_ENTITY_CONFIGS = "google_entity_configs"
PREF_GOOGLE_REPORT_STATE = "google_report_state"
PREF_ALEXA_ENTITY_CONFIGS = "alexa_entity_configs"
PREF_ALEXA_REPORT_STATE = "alexa_report_state"
PREF_OVERRIDE_NAME = "override_name"
PREF_DISABLE_2FA = "disable_2fa"
PREF_ALIASES = "aliases"
PREF_SHOULD_EXPOSE = "should_expose"
PREF_GOOGLE_LOCAL_WEBHOOK_ID = "google_local_webhook_id"
PREF_USERNAME = "username"
PREF_ALEXA_DEFAULT_EXPOSE = "alexa_default_expose"
PREF_GOOGLE_DEFAULT_EXPOSE = "google_default_expose"
PREF_TTS_DEFAULT_VOICE = "tts_default_voice"
DEFAULT_TTS_DEFAULT_VOICE = ("en-US", "female")
DEFAULT_DISABLE_2FA = False
DEFAULT_ALEXA_REPORT_STATE = False
DEFAULT_GOOGLE_REPORT_STATE = False
DEFAULT_EXPOSED_DOMAINS = [
    "climate",
    "cover",
    "fan",
    "humidifier",
    "light",
    "lock",
    "scene",
    "script",
    "sensor",
    "switch",
    "vacuum",
    "water_heater",
]

CONF_ALEXA = "alexa"
CONF_ALIASES = "aliases"
CONF_COGNITO_CLIENT_ID = "cognito_client_id"
CONF_ENTITY_CONFIG = "entity_config"
CONF_FILTER = "filter"
CONF_GOOGLE_ACTIONS = "google_actions"
CONF_RELAYER = "relayer"
CONF_USER_POOL_ID = "user_pool_id"
CONF_SUBSCRIPTION_INFO_URL = "subscription_info_url"
CONF_CLOUDHOOK_CREATE_URL = "cloudhook_create_url"
CONF_REMOTE_API_URL = "remote_api_url"
CONF_ACME_DIRECTORY_SERVER = "acme_directory_server"
CONF_ALEXA_ACCESS_TOKEN_URL = "alexa_access_token_url"
CONF_GOOGLE_ACTIONS_REPORT_STATE_URL = "google_actions_report_state_url"
CONF_ACCOUNT_LINK_URL = "account_link_url"
CONF_VOICE_API_URL = "voice_api_url"

MODE_DEV = "development"
MODE_PROD = "production"

DISPATCHER_REMOTE_UPDATE = "cloud_remote_update"


class RequireRelink(Exception):
    """The skill needs to be relinked."""
