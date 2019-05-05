"""Support for Azure DNS services."""
import logging

from datetime import datetime
from datetime import timedelta

import requests
import aiohttp
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_DOMAIN
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ['adal==1.2.1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'azuredns'

INTERVAL = timedelta(minutes=5)

AUTHORITY_HOST_URL = 'https://login.microsoftonline.com'
RESOURCE = 'https://management.azure.com/'

CONF_CLIENTID = 'clientid'
CONF_CLIENTSECRET = 'clientsecret'
CONF_TENANT = 'tenant'
CONF_SUBSCRIPTIONID = 'subscriptionid'
CONF_RESOURCEGROUPNAME = 'resourcegroupname'
CONF_TTL = 'ttl'
CONF_TIMEOUT = 'timeout'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Optional(CONF_HOST, default='@'): cv.string,
        vol.Required(CONF_TENANT): cv.string,
        vol.Required(CONF_CLIENTID): cv.string,
        vol.Required(CONF_CLIENTSECRET): cv.string,
        vol.Required(CONF_SUBSCRIPTIONID): cv.string,
        vol.Required(CONF_RESOURCEGROUPNAME): cv.string,
        vol.Optional(CONF_TIMEOUT, default=60): cv.byte,
        vol.Optional(CONF_TTL, default=60): cv.byte,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Initialize the Azure DNS component."""
    domain = config[DOMAIN][CONF_DOMAIN]
    host = config[DOMAIN][CONF_HOST]
    resource = RESOURCE
    tenant = config[DOMAIN][CONF_TENANT]
    clientid = config[DOMAIN][CONF_CLIENTID]
    clientsecret = config[DOMAIN][CONF_CLIENTSECRET]
    subscriptionid = config[DOMAIN][CONF_SUBSCRIPTIONID]
    resourcegroupname = config[DOMAIN][CONF_RESOURCEGROUPNAME]
    timeout = config[DOMAIN][CONF_TIMEOUT]
    ttl = config[DOMAIN][CONF_TTL]
    authority_url = AUTHORITY_HOST_URL + "/" + config[DOMAIN][CONF_TENANT]
    api_url = ("https://management.azure.com/subscriptions/" +
               subscriptionid +
               "/resourceGroups/" +
               resourcegroupname +
               "/providers/Microsoft.Network/dnsZones/" +
               domain +
               "/A/" +
               host +
               "?api-version=2018-05-01")

    async_get_clientsession(hass)

    result = await _update_azuredns(resource, tenant,
                                    clientid, clientsecret,
                                    authority_url, api_url, timeout, ttl)

    if not result:
        _LOGGER.error("Failed to update Azure DNS record")
        return False

    async def update_domain_interval():
        """Update the Azure DNS entry."""
        await _update_azuredns(resource, tenant,
                               clientid, clientsecret, authority_url,
                               api_url, timeout, ttl)

    async_track_time_interval(hass, update_domain_interval, INTERVAL)
    return result


async def _update_azuredns(resource, tenant,
                           clientid, clientsecret, authority_url,
                           api_url, timeout, ttl):
    """Update the Azure DNS Record with the external IP address."""
    import adal

    params = {
        'resource': resource,
        'tenant': tenant,
        'clientid': clientid,
        'clientsecret': clientsecret,
        'api_url': api_url,
    }

    # Acquire the Azure AD token.
    context = adal.AuthenticationContext(
        authority_url, validate_authority=['tenant'] != 'adfs',
    )

    token = context.acquire_token_with_client_credentials(
        params['resource'],
        params['clientid'],
        params['clientsecret'])

    access_token = token.get('accessToken')

    if not access_token:
        _LOGGER.error("Failed to acquire Azure AD Access Token")
    else:
        _LOGGER.debug("Azure AD App Token was acquired")

    # Get the external IP address of the Home Assistant instance.
    aiotimeout = aiohttp.ClientTimeout(total=timeout)

    async with aiohttp.ClientSession(timeout=aiotimeout) as aiosession:
        async with aiosession.get('https://api.ipify.org') as aioresp:
            ipv4address = (await aioresp.text())

    if not ipv4address:
        _LOGGER.error("Failed to get external IP address from ipify API")
    else:
        _LOGGER.debug("External IP address is: %s", ipv4address)

    # Create a PATCH request with the Azure Resource Manager REST API.
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/json"
    }
    url = params['api_url']
    payload = {
        "properties": {
            "metadata": {
                "Last_changed_by_Home_Assistant": str(datetime.now())
            },
            "TTL": ttl,
            "ARecords": [
                {
                    "ipv4Address": ipv4address
                }
            ]
        }
    }

    try:
        result = requests.patch(url, json=payload,
                                headers=headers, timeout=timeout).json()

        azureip = result['properties']['ARecords'][0]['ipv4Address']

        if ipv4address == azureip:
            _LOGGER.debug(
                "IP address in Azure DNS configured correctly to %s",
                ipv4address)
        else:
            _LOGGER.error(
                "External IP address %s does not match IP from Azure DNS %s",
                ipv4address, azureip)
            return False

    except requests.exceptions.RequestException as errormessage:
        _LOGGER.error("Azure DNS patch request failed: %s", errormessage)
        return False

    return True
