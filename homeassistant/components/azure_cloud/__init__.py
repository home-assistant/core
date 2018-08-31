"""
Azure component that handles interaction with Microsoft Azure Cloud.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/azure_cloud/
"""
import asyncio
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['azure-mgmt-compute==2.0.0']
DEPENDENCIES = []
DOMAIN = 'azure_cloud'

CONF_TENANT_ID = 'tenant_id'
CONF_SUBSCRIPTION_ID = 'subscription_id'
CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_TENANT_ID): cv.string,
        vol.Required(CONF_SUBSCRIPTION_ID): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the azure component."""
    conf = config.get(DOMAIN, {})
    hass.data[DOMAIN] = AzureSubscription(hass, conf)
    return True


class AzureSubscription:
    """Representation of an azure subscription."""

    def __init__(self, hass, config):
        """Initialize the azure subscription Entity."""
        from azure.common.credentials import ServicePrincipalCredentials
        self._tenant_id = config.get(CONF_TENANT_ID)
        self._subscription_id = config.get(CONF_SUBSCRIPTION_ID)
        self._client_id = config.get(CONF_CLIENT_ID)
        self._client_secret = config.get(CONF_CLIENT_SECRET)
        self._credentials = ServicePrincipalCredentials(
            client_id=self._client_id, secret=self._client_secret,
            tenant=self._tenant_id)
        _LOGGER.debug(
            "Azure subscription entity initialized for subscription %s.",
            self._subscription_id)

    @property
    def credentials(self):
        """Return the credentials of the azure subscription."""
        return self._credentials

    @property
    def subscription_id(self):
        """Return the ID of the azure subscription."""
        return self._subscription_id
