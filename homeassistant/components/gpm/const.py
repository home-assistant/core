"""Constants for the GPM integration."""

DOMAIN = "gpm"

CONF_UPDATE_STRATEGY = "update_strategy"
CONF_DOWNLOAD_URL = "download_url"

PATH_CLONE_BASEDIR = DOMAIN
PATH_INTEGRATION_INSTALL_BASEDIR = "custom_components"
PATH_RESOURCE_INSTALL_BASEDIR = f"{PATH_CLONE_BASEDIR}/_resources"

URL_BASE = "/gpm"

GIT_SHORT_HASH_LEN = 7
DOWNLOAD_CHUNK_SIZE = 5 * 2**20  # 2MB
