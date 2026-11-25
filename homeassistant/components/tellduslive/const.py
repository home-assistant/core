"""Consts used by TelldusLive."""

from datetime import timedelta

APPLICATION_NAME = "Home Assistant"

DOMAIN = "tellduslive"

SIGNAL_UPDATE_ENTITY = "tellduslive_update"

KEY_SESSION = "session"
KEY_SCAN_INTERVAL = "scan_interval"

CONF_TOKEN_SECRET = "token_secret"

PUBLIC_KEY = "THUPUNECH5YEQA3RE6UYUPRUZ2DUGUGA"
NOT_SO_PRIVATE_KEY = "PHES7U2RADREWAFEBUSTUBAWRASWUTUS"

SCAN_INTERVAL = timedelta(minutes=1)

ATTR_LAST_UPDATED = "time_last_updated"

TELLDUS_DISCOVERY_NEW = "telldus_new_{}_{}"

CLOUD_NAME = "Cloud API"
