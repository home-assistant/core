"""Constants for the cloud component."""
DOMAIN = 'cloud'
REQUEST_TIMEOUT = 10

PREF_ENABLE_ALEXA = 'alexa_enabled'
PREF_ENABLE_GOOGLE = 'google_enabled'
PREF_ENABLE_REMOTE = 'remote_enabled'
PREF_GOOGLE_SECURE_DEVICES_PIN = 'google_secure_devices_pin'
PREF_CLOUDHOOKS = 'cloudhooks'
PREF_CLOUD_USER = 'cloud_user'

CONF_ALEXA = 'alexa'
CONF_ALIASES = 'aliases'
CONF_COGNITO_CLIENT_ID = 'cognito_client_id'
CONF_ENTITY_CONFIG = 'entity_config'
CONF_FILTER = 'filter'
CONF_GOOGLE_ACTIONS = 'google_actions'
CONF_RELAYER = 'relayer'
CONF_USER_POOL_ID = 'user_pool_id'
CONF_GOOGLE_ACTIONS_SYNC_URL = 'google_actions_sync_url'
CONF_SUBSCRIPTION_INFO_URL = 'subscription_info_url'
CONF_CLOUDHOOK_CREATE_URL = 'cloudhook_create_url'
CONF_REMOTE_API_URL = 'remote_api_url'
CONF_ACME_DIRECTORY_SERVER = 'acme_directory_server'

MODE_DEV = "development"
MODE_PROD = "production"

DISPATCHER_REMOTE_UPDATE = 'cloud_remote_update'


class InvalidTrustedNetworks(Exception):
    """Raised when invalid trusted networks config."""
