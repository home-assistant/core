"""Constants for testing AEH."""
from homeassistant.components.azure_event_hub.const import (
    CONF_EVENT_HUB_CON_STRING,
    CONF_EVENT_HUB_INSTANCE_NAME,
    CONF_EVENT_HUB_NAMESPACE,
    CONF_EVENT_HUB_SAS_KEY,
    CONF_EVENT_HUB_SAS_POLICY,
    CONF_MAX_DELAY,
    CONF_SEND_INTERVAL,
    CONF_USE_CONN_STRING,
)

AZURE_EVENT_HUB_PATH = "homeassistant.components.azure_event_hub"
PRODUCER_PATH = f"{AZURE_EVENT_HUB_PATH}.client.EventHubProducerClient"
CLIENT_PATH = f"{AZURE_EVENT_HUB_PATH}.client.AzureEventHubClient"
CONFIG_FLOW_PATH = f"{AZURE_EVENT_HUB_PATH}.config_flow"

BASE_CONFIG_CS = {
    CONF_EVENT_HUB_INSTANCE_NAME: "test-instance",
    CONF_USE_CONN_STRING: True,
}
BASE_CONFIG_SAS = {
    CONF_EVENT_HUB_INSTANCE_NAME: "test-instance",
    CONF_USE_CONN_STRING: False,
}

CS_CONFIG = {CONF_EVENT_HUB_CON_STRING: "test-cs"}
SAS_CONFIG = {
    CONF_EVENT_HUB_NAMESPACE: "test-ns",
    CONF_EVENT_HUB_SAS_POLICY: "test-policy",
    CONF_EVENT_HUB_SAS_KEY: "test-key",
}
CS_CONFIG_FULL = {
    CONF_EVENT_HUB_INSTANCE_NAME: "test-instance",
    CONF_EVENT_HUB_CON_STRING: "test-cs",
}
SAS_CONFIG_FULL = {
    CONF_EVENT_HUB_INSTANCE_NAME: "test-instance",
    CONF_EVENT_HUB_NAMESPACE: "test-ns",
    CONF_EVENT_HUB_SAS_POLICY: "test-policy",
    CONF_EVENT_HUB_SAS_KEY: "test-key",
}

IMPORT_CONFIG = {
    CONF_EVENT_HUB_INSTANCE_NAME: "test-instance",
    CONF_EVENT_HUB_NAMESPACE: "test-ns",
    CONF_EVENT_HUB_SAS_POLICY: "test-policy",
    CONF_EVENT_HUB_SAS_KEY: "test-key",
    CONF_SEND_INTERVAL: 5,
    CONF_MAX_DELAY: 10,
}

BASIC_OPTIONS = {
    CONF_SEND_INTERVAL: 5,
}
UPDATE_OPTIONS = {CONF_SEND_INTERVAL: 100}
