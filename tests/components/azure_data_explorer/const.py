"""Constants for testing Azure Data Explorer."""

from homeassistant.components.azure_data_explorer.const import (
    CONF_ADX_CLUSTER_INGEST_URI,
    CONF_ADX_DATABASE_NAME,
    CONF_ADX_TABLE_NAME,
    CONF_APP_REG_ID,
    CONF_APP_REG_SECRET,
    CONF_AUTHORITY_ID,
    CONF_SEND_INTERVAL,
    CONF_USE_FREE,
)

AZURE_DATA_EXPLORER_PATH = "homeassistant.components.azure_data_explorer"
CLIENT_PATH = f"{AZURE_DATA_EXPLORER_PATH}.AzureDataExplorer"


BASE_DB = {
    CONF_ADX_DATABASE_NAME: "test-database-name",
    CONF_ADX_TABLE_NAME: "test-table-name",
    CONF_APP_REG_ID: "test-app-reg-id",
    CONF_APP_REG_SECRET: "test-app-reg-secret",
    CONF_AUTHORITY_ID: "test-auth-id",
}


BASE_CONFIG_URI = {
    CONF_ADX_CLUSTER_INGEST_URI: "https://cluster.region.kusto.windows.net"
}

BASIC_OPTIONS = {
    CONF_USE_FREE: False,
    CONF_SEND_INTERVAL: 5,
}

BASE_CONFIG = BASE_DB | BASE_CONFIG_URI
BASE_CONFIG_FULL = BASE_CONFIG | BASIC_OPTIONS | BASE_CONFIG_URI


BASE_CONFIG_IMPORT = {
    CONF_ADX_CLUSTER_INGEST_URI: "https://cluster.region.kusto.windows.net",
    CONF_USE_FREE: False,
    CONF_SEND_INTERVAL: 5,
}

FREE_OPTIONS = {CONF_USE_FREE: True, CONF_SEND_INTERVAL: 5}

BASE_CONFIG_FREE = BASE_CONFIG | FREE_OPTIONS
