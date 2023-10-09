from datetime import timedelta

DOMAIN = "tedee"
NAME = "Tedee"

SCAN_INTERVAL = timedelta(seconds=10)

CONF_UNLOCK_PULLS_LATCH = "unlock_pulls_latch"
CONF_LOCAL_ACCESS_TOKEN = "local_access_token"
CONF_HOME_ASSISTANT_ACCESS_TOKEN = "home_assistant_access_token"
CONF_USE_CLOUD = "use_cloud"