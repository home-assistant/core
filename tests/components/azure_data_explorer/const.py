"""Constants for testing AEH."""
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


BASE_CONFIG = {
    CONF_ADX_CLUSTER_INGEST_URI: "https://cluster.region.kusto.windows.net",
    CONF_ADX_DATABASE_NAME: "test-database-name",
    CONF_ADX_TABLE_NAME: "test-table-name",
    CONF_APP_REG_ID: "test-app-reg-id",
    CONF_APP_REG_SECRET: "test-app-reg-secret",
    CONF_AUTHORITY_ID: "test-auth-id",
    CONF_USE_FREE: False,
}

BASE_CONFIG_FULL = {
    CONF_ADX_CLUSTER_INGEST_URI: "https://cluster.region.kusto.windows.net",
    CONF_ADX_DATABASE_NAME: "test-database-name",
    CONF_ADX_TABLE_NAME: "test-table-name",
    CONF_APP_REG_ID: "test-app-reg-id",
    CONF_APP_REG_SECRET: "test-app-reg-secret",
    CONF_AUTHORITY_ID: "test-auth-id",
    CONF_USE_FREE: False,
    CONF_SEND_INTERVAL: 5,
}

BASE_CONFIG_IMPORT = {
    CONF_USE_FREE: False,
    CONF_SEND_INTERVAL: 5,
}


BASE_CONFIG_FREE = {
    CONF_ADX_CLUSTER_INGEST_URI: "https://cluster.region.kusto.windows.net",
    CONF_ADX_DATABASE_NAME: "test-database-name",
    CONF_ADX_TABLE_NAME: "test-table-name",
    CONF_APP_REG_ID: "test-app-reg-id",
    CONF_APP_REG_SECRET: "test-app-reg-secret",
    CONF_AUTHORITY_ID: "test-auth-id",
    CONF_USE_FREE: True,
    CONF_SEND_INTERVAL: 5,
}

IMPORT_CONFIG = {
    CONF_ADX_CLUSTER_INGEST_URI: "https://cluster.region.kusto.windows.net",
    CONF_ADX_DATABASE_NAME: "test-database-name",
    CONF_ADX_TABLE_NAME: "test-table-name",
    CONF_APP_REG_ID: "test-app-reg-id",
    CONF_APP_REG_SECRET: "test-app-reg-secret",
    CONF_AUTHORITY_ID: "test-auth-id",
    CONF_USE_FREE: False,
    CONF_SEND_INTERVAL: 5,
}


IMPORT_CONFIG = {}

BASIC_OPTIONS = {
    CONF_SEND_INTERVAL: 5,
}
UPDATE_OPTIONS = {CONF_SEND_INTERVAL: 100}
