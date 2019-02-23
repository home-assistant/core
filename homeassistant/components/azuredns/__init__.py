"""Support for Azure DNS services."""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_DOMAIN
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ['adal==1.2.1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'azuredns'

INTERVAL = timedelta(minutes=5)

AUTHORITYHOSTURL = 'https://login.microsoftonline.com'
RESOURCE = 'https://management.azure.com/'

CONF_CLIENTID = 'clientid'
CONF_CLIENTSECRET = 'clientsecret'
CONF_TENANT = 'tenant'
CONF_SUBSCRIPTIONID = 'subscriptionid'
CONF_RESOURCEGROUPNAME = 'resourcegroupname'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Optional(CONF_HOST, default='@'): cv.string,
        vol.Required(CONF_TENANT): cv.string,
        vol.Required(CONF_CLIENTID): cv.string,
        vol.Required(CONF_CLIENTSECRET): cv.string,
        vol.Required(CONF_SUBSCRIPTIONID): cv.string,
        vol.Required(CONF_RESOURCEGROUPNAME): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Initialize the Azure DNS component."""
    domain = config[DOMAIN][CONF_DOMAIN]
    host = config[DOMAIN][CONF_HOST]
    resource = (RESOURCE)
    tenant = config[DOMAIN][CONF_TENANT]
    clientid = config[DOMAIN][CONF_CLIENTID]
    clientsecret = config[DOMAIN][CONF_CLIENTSECRET]
    authority_url = (AUTHORITYHOSTURL + '/' + config[DOMAIN][CONF_TENANT])
    apiurl = ('https://management.azure.com/subscriptions/' + config[DOMAIN][CONF_SUBSCRIPTIONID] + '/resourceGroups/' + config[DOMAIN][CONF_RESOURCEGROUPNAME] + 'providers/Microsoft.Network/dnsZones/' + config[DOMAIN][CONF_DOMAIN] + '/A/' + config[DOMAIN][CONF_HOST] + '?api-version=2018-03-01-preview')

    session = async_get_clientsession(hass)

    result = await _update_azuredns(session, domain, host, resource, tenant, clientid, clientsecret, authority_url, apiurl)

    if not result:
        return False

    async def update_domain_interval(now):
        """Update the Azure DNS entry."""
        await _update_azuredns(session, domain, host, resource, tenant, clientid, clientsecret, authority_url, apiurl)

    async_track_time_interval(hass, update_domain_interval, INTERVAL)

    return result


async def _update_azuredns(session, domain, host, resource, tenant, clientid, clientsecret, authority_url, apiurl):
    import adal
    import json

    params = {
        'domain': domain,
        'host': host,
        'resource': resource,
        'tenant': tenant,
        'clientid': clientid,
        'clientsecret': clientsecret,
        'apiurl': apiurl,
    }

    """Requesting the Azure AD App Token by using ADAL."""
    context = adal.AuthenticationContext(
        authority_url, validate_authority=['tenant'] != 'adfs',
    )

    token = context.acquire_token_with_client_credentials(
        params['resource'],
        params['clientid'],
        params['clientsecret'])

    access_token = token.get('accessToken')

    _LOGGER.debug("Azure AD App Token is:\n" + json.dumps(token, indent=2))

    """Update the DNS entry by using the Azure REST API."""
    import requests
    from datetime import datetime

    ipv4Address = requests.get('https://api.ipify.org').text

    _LOGGER.debug("External IP address is: " + ipv4Address)

    headers = {
        "Authorization": 'Bearer ' + access_token,
        "Content-Type": 'application/json'
    }
    url = params['apiurl']
    payload = {
        "properties": {
            "metadata": {
                "Last_changed_by_Home_Assistant": str(datetime.now())
            },
            "TTL": 60,
            "ARecords": [
                {
                    "ipv4Address": ipv4Address
                }
            ]
        }
    }

    try:
        requests.patch(url, json=payload, headers=headers).json()

    except requests.exceptions.RequestException as errormessage:
        _LOGGER.error(errormessage)
        return False

    return True