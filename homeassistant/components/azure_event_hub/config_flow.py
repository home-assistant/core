"""Config flow for Azure Event Hub integration."""
import logging

import voluptuous as vol

from azure.eventhub import (
    EventHubProducerClient,
    EventHubSharedKeyCredential,
    ConnectError,
)

from homeassistant import core, config_entries, exceptions
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from .const import DOMAIN  # pylint:disable=unused-import
from .const import (
    CONF_EVENT_HUB_CON_STRING,
    CONF_EVENT_HUB_INSTANCE_NAME,
    CONF_EVENT_HUB_NAMESPACE,
    CONF_EVENT_HUB_SAS_KEY,
    CONF_EVENT_HUB_SAS_POLICY,
    CONF_FILTER,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EVENT_HUB_NAMESPACE): str,
        vol.Required(CONF_EVENT_HUB_INSTANCE_NAME): str,
        vol.Required(CONF_EVENT_HUB_SAS_POLICY): str,
        vol.Required(CONF_EVENT_HUB_SAS_KEY): str,
    }
)


@callback
def configured_instances(hass):
    """Return a set of configured AEH instances."""
    _LOGGER.info("Configured Instances")
    return set(entry.title for entry in hass.config_entries.async_entries(DOMAIN))


async def validate_input(hass: core.HomeAssistant, data, config=True):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    _LOGGER.info("Validating input from %s.", "config" if config else "yaml")
    _LOGGER.debug("Config: %s", data)
    if config:
        client_args = {
            "host": f"{data[CONF_EVENT_HUB_NAMESPACE]}.servicebus.windows.net",
            "credential": EventHubSharedKeyCredential(
                policy=data[CONF_EVENT_HUB_SAS_POLICY], key=data[CONF_EVENT_HUB_SAS_KEY]
            ),
            "event_hub_path": data[CONF_EVENT_HUB_INSTANCE_NAME],
        }
        conn_str_client = False
    else:
        data = data[DOMAIN]
        if CONF_EVENT_HUB_CON_STRING in data:
            client_args = {"conn_str": data[CONF_EVENT_HUB_CON_STRING]}
            conn_str_client = True
        else:
            client_args = {
                "host": f"{data[CONF_EVENT_HUB_NAMESPACE]}.servicebus.windows.net",
                "credential": EventHubSharedKeyCredential(
                    policy=data[CONF_EVENT_HUB_SAS_POLICY],
                    key=data[CONF_EVENT_HUB_SAS_KEY],
                ),
                "event_hub_path": data[CONF_EVENT_HUB_INSTANCE_NAME],
            }
            conn_str_client = False
    try:
        if conn_str_client:
            client = EventHubProducerClient.from_connection_string(**client_args)
        else:
            client = EventHubProducerClient(**client_args)
        client.close()
        return {"title": data[CONF_EVENT_HUB_NAMESPACE]}
    except ConnectError:
        raise CannotConnect


@config_entries.HANDLERS.register(DOMAIN)
class AzureEventHubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Azure Event Hub."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config, config=True)

    async def async_step_user(self, user_input=None, config=True):
        """Handle the initial step."""
        _LOGGER.info("Setting up steps.")
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input, config)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
