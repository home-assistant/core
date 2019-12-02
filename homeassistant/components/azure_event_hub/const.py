"""Constants and shared schema for the Azure Event Hub integration."""
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    CONF_EXCLUDE_DOMAINS,
    CONF_EXCLUDE_ENTITIES,
    CONF_INCLUDE_DOMAINS,
    CONF_INCLUDE_ENTITIES,
)

DOMAIN = "azure_event_hub"

CONF_EVENT_HUB_NAMESPACE = "event_hub_namespace"
CONF_EVENT_HUB_INSTANCE_NAME = "event_hub_instance_name"
CONF_EVENT_HUB_SAS_POLICY = "event_hub_sas_policy"
CONF_EVENT_HUB_SAS_KEY = "event_hub_sas_key"
CONF_EVENT_HUB_CON_STRING = "event_hub_connection_string"
CONF_FILTER = "filter"

FILTER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_INCLUDE_DOMAINS, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Optional(CONF_INCLUDE_ENTITIES, default=[]): cv.entity_ids,
            vol.Optional(CONF_EXCLUDE_DOMAINS, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Optional(CONF_EXCLUDE_ENTITIES, default=[]): cv.entity_ids,
        }
    )
)
