"""Consts used by TelldusLive."""
from datetime import timedelta

from homeassistant.const import (  # noqa pylint: disable=unused-import
    ATTR_BATTERY_LEVEL, CONF_HOST, CONF_TOKEN, DEVICE_DEFAULT_NAME)

APPLICATION_NAME = 'Home Assistant'

DOMAIN = 'tellduslive'

TELLDUS_CONFIG_FILE = 'tellduslive.conf'
KEY_CONFIG = 'tellduslive_config'

SIGNAL_UPDATE_ENTITY = 'tellduslive_update'

KEY_SESSION = 'session'
KEY_SCAN_INTERVAL = 'scan_interval'

CONF_TOKEN_SECRET = 'token_secret'

PUBLIC_KEY = 'THUPUNECH5YEQA3RE6UYUPRUZ2DUGUGA'
NOT_SO_PRIVATE_KEY = 'PHES7U2RADREWAFEBUSTUBAWRASWUTUS'

MIN_UPDATE_INTERVAL = timedelta(seconds=5)
SCAN_INTERVAL = timedelta(minutes=1)

ATTR_LAST_UPDATED = 'time_last_updated'

SIGNAL_UPDATE_ENTITY = 'tellduslive_update'
TELLDUS_DISCOVERY_NEW = 'telldus_new_{}_{}'

CLOUD_NAME = 'Cloud API'
