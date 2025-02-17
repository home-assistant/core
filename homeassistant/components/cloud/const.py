"""Constants for the cloud component."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.util.hass_dict import HassKey
from homeassistant.util.signal_type import SignalType

if TYPE_CHECKING:
    from hass_nabucasa import Cloud

    from .client import CloudClient
    from .helpers import FixedSizeQueueLogHandler

DOMAIN = "cloud"
DATA_CLOUD: HassKey[Cloud[CloudClient]] = HassKey(DOMAIN)
DATA_PLATFORMS_SETUP: HassKey[dict[str, asyncio.Event]] = HassKey(
    "cloud_platforms_setup"
)
DATA_CLOUD_LOG_HANDLER: HassKey[FixedSizeQueueLogHandler] = HassKey("cloud_log_handler")
EVENT_CLOUD_EVENT = "cloud_event"

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
PREF_INSTANCE_ID = "instance_id"
PREF_SHOULD_EXPOSE = "should_expose"
PREF_GOOGLE_LOCAL_WEBHOOK_ID = "google_local_webhook_id"
PREF_USERNAME = "username"
PREF_REMOTE_DOMAIN = "remote_domain"
PREF_ALEXA_DEFAULT_EXPOSE = "alexa_default_expose"
PREF_GOOGLE_DEFAULT_EXPOSE = "google_default_expose"
PREF_ALEXA_SETTINGS_VERSION = "alexa_settings_version"
PREF_GOOGLE_SETTINGS_VERSION = "google_settings_version"
PREF_TTS_DEFAULT_VOICE = "tts_default_voice"
PREF_GOOGLE_CONNECTED = "google_connected"
PREF_REMOTE_ALLOW_REMOTE_ENABLE = "remote_allow_remote_enable"
PREF_ENABLE_CLOUD_ICE_SERVERS = "cloud_ice_servers_enabled"
DEFAULT_TTS_DEFAULT_VOICE = ("en-US", "JennyNeural")
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
CONF_CLOUDHOOK_SERVER = "cloudhook_server"
CONF_RELAYER_SERVER = "relayer_server"
CONF_REMOTESTATE_SERVER = "remotestate_server"
CONF_THINGTALK_SERVER = "thingtalk_server"
CONF_SERVICEHANDLERS_SERVER = "servicehandlers_server"

MODE_DEV = "development"
MODE_PROD = "production"

DISPATCHER_REMOTE_UPDATE: SignalType[Any] = SignalType("cloud_remote_update")

STT_ENTITY_UNIQUE_ID = "cloud-speech-to-text"
TTS_ENTITY_UNIQUE_ID = "cloud-text-to-speech"

LOGIN_MFA_TIMEOUT = 60
