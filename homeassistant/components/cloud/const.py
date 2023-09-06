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
PREF_DISABLE_2FA = "disable_2fa"
PREF_SHOULD_EXPOSE = "should_expose"
PREF_GOOGLE_LOCAL_WEBHOOK_ID = "google_local_webhook_id"
PREF_USERNAME = "username"
PREF_REMOTE_DOMAIN = "remote_domain"
PREF_ALEXA_DEFAULT_EXPOSE = "alexa_default_expose"
PREF_GOOGLE_DEFAULT_EXPOSE = "google_default_expose"
PREF_ALEXA_SETTINGS_VERSION = "alexa_settings_version"
PREF_GOOGLE_SETTINGS_VERSION = "google_settings_version"
PREF_TTS_DEFAULT_VOICE = "tts_default_voice"
DEFAULT_TTS_DEFAULT_VOICE = ("en-US", "female")
DEFAULT_DISABLE_2FA = False
DEFAULT_ALEXA_REPORT_STATE = True
DEFAULT_GOOGLE_REPORT_STATE = True
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
CONF_USER_POOL_ID = "user_pool_id"

CONF_ACCOUNT_LINK_SERVER = "account_link_server"
CONF_ACCOUNTS_SERVER = "accounts_server"
CONF_ACME_SERVER = "acme_server"
CONF_ALEXA_SERVER = "alexa_server"
CONF_CLOUDHOOK_SERVER = "cloudhook_server"
CONF_RELAYER_SERVER = "relayer_server"
CONF_REMOTE_SNI_SERVER = "remote_sni_server"
CONF_REMOTESTATE_SERVER = "remotestate_server"
CONF_THINGTALK_SERVER = "thingtalk_server"
CONF_SERVICEHANDLERS_SERVER = "servicehandlers_server"

MODE_DEV = "development"
MODE_PROD = "production"

DISPATCHER_REMOTE_UPDATE = "cloud_remote_update"
