"""
Azure component that handles interaction with Microsoft Azure Cloud.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/azure/
"""

import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['azure-mgmt-compute==4.0.1']
DOMAIN = 'azure'

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


def setup(hass, config):
    """Set up the azure component."""
    from azure.common.exceptions import AuthenticationError, \
        ClientRequestError, CloudError, HttpOperationError
    from azure.common.credentials import ServicePrincipalCredentials

    conf = config[DOMAIN]
    subscription_id = conf[CONF_SUBSCRIPTION_ID]
    try:
        credentials = ServicePrincipalCredentials(
            client_id=conf[CONF_CLIENT_ID], secret=conf[CONF_CLIENT_SECRET],
            tenant=conf[CONF_TENANT_ID])
        hass.data[DOMAIN] = AzureSubscription(subscription_id, credentials)
        _LOGGER.debug(
            "Azure subscription entity initialized for subscription %s",
            subscription_id)
        return True
    except AuthenticationError:
        _LOGGER.error(
            "Azure authentication failed for subscription %s",
            subscription_id)
        return False
    except (ClientRequestError, CloudError, HttpOperationError):
        _LOGGER.error(
            "Azure subscription entity initialization failed for %s",
            subscription_id)
    return False


class AzureSubscription:
    """Representation of an azure subscription."""

    def __init__(self, subscription_id, credentials):
        """Initialize the azure subscription Entity."""
        self._subscription_id = subscription_id
        self._credentials = credentials

    @property
    def credentials(self):
        """Return the credentials of the azure subscription."""
        return self._credentials

    @property
    def subscription_id(self):
        """Return the ID of the azure subscription."""
        return self._subscription_id
