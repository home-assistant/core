"""Constants for the Azure Data Explorer integration."""

from __future__ import annotations

from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

DOMAIN = "azure_data_explorer"

CONF_ADX_CLUSTER_INGEST_URI = "cluster_ingest_uri"
CONF_ADX_DATABASE_NAME = "database"
CONF_ADX_TABLE_NAME = "table"
CONF_APP_REG_ID = "client_id"
CONF_APP_REG_SECRET = "client_secret"
CONF_AUTHORITY_ID = "authority_id"
CONF_SEND_INTERVAL = "send_interval"
CONF_MAX_DELAY = "max_delay"
CONF_FILTER = DATA_FILTER = "filter"
CONF_USE_FREE = "use_queued_ingestion"
DATA_HUB = "hub"
STEP_USER = "user"


DEFAULT_SEND_INTERVAL: int = 5
DEFAULT_MAX_DELAY: int = 30
DEFAULT_OPTIONS: dict[str, Any] = {CONF_SEND_INTERVAL: DEFAULT_SEND_INTERVAL}

ADDITIONAL_ARGS: dict[str, Any] = {"logging_enable": False}
FILTER_STATES = (STATE_UNKNOWN, STATE_UNAVAILABLE)
