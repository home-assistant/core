"""Constants and shared schema for the Azure Event Hub integration."""

from __future__ import annotations

from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

DOMAIN = "azure_event_hub"

CONF_USE_CONN_STRING = "use_connection_string"
CONF_EVENT_HUB_NAMESPACE = "event_hub_namespace"
CONF_EVENT_HUB_INSTANCE_NAME = "event_hub_instance_name"
CONF_EVENT_HUB_SAS_POLICY = "event_hub_sas_policy"
CONF_EVENT_HUB_SAS_KEY = "event_hub_sas_key"
CONF_EVENT_HUB_CON_STRING = "event_hub_connection_string"
CONF_SEND_INTERVAL = "send_interval"
CONF_MAX_DELAY = "max_delay"
CONF_FILTER = DATA_FILTER = "filter"
DATA_HUB = "hub"

STEP_USER = "user"
STEP_SAS = "sas"
STEP_CONN_STRING = "conn_string"

DEFAULT_SEND_INTERVAL: int = 5
DEFAULT_MAX_DELAY: int = 30
DEFAULT_OPTIONS: dict[str, Any] = {
    CONF_SEND_INTERVAL: DEFAULT_SEND_INTERVAL,
}

ADDITIONAL_ARGS: dict[str, Any] = {"logging_enable": False}
FILTER_STATES = (STATE_UNKNOWN, STATE_UNAVAILABLE, "")
