"""Support for Azure Event Hubs."""
from __future__ import annotations

import logging

from azure.eventhub.exceptions import EventHubError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_EVENT_HUB_CON_STRING,
    CONF_EVENT_HUB_INSTANCE_NAME,
    CONF_EVENT_HUB_NAMESPACE,
    CONF_EVENT_HUB_SAS_KEY,
    CONF_EVENT_HUB_SAS_POLICY,
    CONF_FILTER,
    CONF_MAX_DELAY,
    CONF_SEND_INTERVAL,
    DATA_FILTER,
    DATA_HUB,
    DOMAIN,
)
from .hub import AzureEventHub

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_EVENT_HUB_INSTANCE_NAME): cv.string,
                vol.Optional(CONF_EVENT_HUB_CON_STRING): cv.string,
                vol.Optional(CONF_EVENT_HUB_NAMESPACE): cv.string,
                vol.Optional(CONF_EVENT_HUB_SAS_POLICY): cv.string,
                vol.Optional(CONF_EVENT_HUB_SAS_KEY): cv.string,
                vol.Optional(CONF_SEND_INTERVAL): cv.positive_int,
                vol.Optional(CONF_MAX_DELAY): cv.positive_int,
                vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
            },
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, yaml_config: ConfigType) -> bool:
    """Activate Azure EH component from yaml.

    Adds an empty filter to hass data.
    Tries to get a filter from yaml, if present set to hass data.
    If config is empty after getting the filter, return, otherwise emit
    deprecated warning and pass the rest to the config flow.
    """
    hass.data.setdefault(DOMAIN, {DATA_FILTER: FILTER_SCHEMA({})})
    if DOMAIN not in yaml_config:
        return True
    hass.data[DOMAIN][DATA_FILTER] = yaml_config[DOMAIN].pop(CONF_FILTER)

    if not yaml_config[DOMAIN]:
        return True
    _LOGGER.warning(
        "Loading Azure Event Hub completely via yaml config is deprecated; Only the \
        Filter can be set in yaml, the rest is done through a config flow and has \
        been imported, all other keys but filter can be deleted from configuration.yaml"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=yaml_config[DOMAIN]
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Do the setup based on the config entry and the filter from yaml."""
    hass.data.setdefault(DOMAIN, {DATA_FILTER: FILTER_SCHEMA({})})
    hub = AzureEventHub(
        hass,
        entry,
        hass.data[DOMAIN][DATA_FILTER],
    )
    try:
        await hub.async_test_connection()
    except EventHubError as err:
        raise ConfigEntryNotReady("Could not connect to Azure Event Hub") from err
    hass.data[DOMAIN][DATA_HUB] = hub
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    await hub.async_start()
    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for options."""
    hass.data[DOMAIN][DATA_HUB].update_options(entry.options)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hub = hass.data[DOMAIN].pop(DATA_HUB)
    await hub.async_stop()
    return True
