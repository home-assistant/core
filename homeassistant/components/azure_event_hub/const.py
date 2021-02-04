"""Constants and shared schema for the Azure Event Hub integration."""
DOMAIN = "azure_event_hub"

CONF_EVENT_HUB_NAMESPACE = "event_hub_namespace"
CONF_EVENT_HUB_INSTANCE_NAME = "event_hub_instance_name"
CONF_EVENT_HUB_SAS_POLICY = "event_hub_sas_policy"
CONF_EVENT_HUB_SAS_KEY = "event_hub_sas_key"
CONF_EVENT_HUB_CON_STRING = "event_hub_connection_string"
CONF_SEND_INTERVAL = "send_interval"
CONF_MAX_DELAY = "max_delay"
CONF_FILTER = "filter"

ADDITIONAL_ARGS = {"logging_enable": False}
