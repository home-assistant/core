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
    DOMAIN,
)
from .hub import AzureEventHub
from .models import AzureEventHubClient

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
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, yaml_config: ConfigType) -> bool:
    """Activate Azure EH component."""
    config = yaml_config.get(DOMAIN, None)
    if config is None:
        hass.data.setdefault(DOMAIN, {CONF_FILTER: {}})
        return True
    conf_filter = config.pop(CONF_FILTER, {})
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = {CONF_FILTER: conf_filter}
    if config == {}:
        return True
    _LOGGER.warning(
        "Loading Azure Event Hub completely via yaml config is deprecated; Only the Filter can be set in yaml, the rest is done through a config flow and has been imported, all other keys then filter can be deleted from configuration.yaml"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Do the setup based on the config entry and the filter from yaml."""
    client_config = AzureEventHubClient.from_input(**entry.data)
    try:
        await client_config.test_connection()
    except EventHubError as err:
        raise ConfigEntryNotReady from err
    instance = hass.data[DOMAIN]["hub"] = AzureEventHub(
        hass,
        client_config,
        hass.data[DOMAIN][CONF_FILTER],
        entry.options[CONF_SEND_INTERVAL],
        entry.options[CONF_MAX_DELAY],
    )
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    hass.async_create_task(instance.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hub = hass.data[DOMAIN].pop("hub")
    await hub.async_shutdown(None)
    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Update listener for options."""
    instance = hass.data[DOMAIN]["hub"]
    instance.send_interval = entry.options[CONF_SEND_INTERVAL]
    instance.max_delay = entry.options[CONF_MAX_DELAY] + instance.send_interval
