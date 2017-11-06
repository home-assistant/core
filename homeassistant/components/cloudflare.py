"""
Integrate with Cloudflare DDNS.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/cloudflare/
"""
import aiohttp
import async_timeout
import asyncio
import json
import logging
import random
import re
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_API_KEY, CONF_DOMAIN, CONF_EMAIL, CONF_SCAN_INTERVAL, CONF_TIMEOUT,
    CONF_ZONE, HTTP_OK)

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'cloudflare'

CONF_PROXIED = 'proxied'
CONF_RECORD_TYPE = 'record_type'
CONF_TTL = 'ttl'

DEFAULT_TIMEOUT = 10
DEFAULT_TTL = 1
DEFAULT_SCAN_INTERVAL = 5 * 60

RECORD_TYPES = [
    'A',
    'AAAA',
    'CNAME',
]

RECORD_TYPE_VALIDATION = vol.In(RECORD_TYPES)
TTL_VALIDATION = vol.Any(vol.Equal(1), vol.Range(min=120, max=2147483647))

API_BASE_URL = 'https://api.cloudflare.com/client/v4/zones/{}/dns_records'
UPDATE_URL = API_BASE_URL + '/{}'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_DOMAIN): vol.FqdnUrl(),
        vol.Required(CONF_EMAIL): vol.Email(),
        vol.Required(CONF_RECORD_TYPE): RECORD_TYPE_VALIDATION,
        vol.Required(CONF_ZONE): cv.string,
        vol.Optional(CONF_PROXIED, default=False): cv.boolean,
        vol.Optional(CONF_SCAN_INTERVAL,
                     default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_TTL, default=DEFAULT_TTL): TTL_VALIDATION
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the Cloudflare component."""
    api_key = config[DOMAIN].get(CONF_API_KEY)
    domain = re.sub('http.*//', '', config[DOMAIN].get(CONF_DOMAIN))
    email = config[DOMAIN].get(CONF_EMAIL)
    record_type = config[DOMAIN].get(CONF_RECORD_TYPE)
    zone = config[DOMAIN].get(CONF_ZONE)
    proxied = config[DOMAIN].get(CONF_PROXIED)
    scan_interval = config[DOMAIN].get(CONF_SCAN_INTERVAL)
    timeout = config[DOMAIN].get(CONF_TIMEOUT)
    ttl = config[DOMAIN].get(CONF_TTL)

    session = hass.helpers.aiohttp_client.async_get_clientsession()

    result = yield from _update_cloudflare(
        hass, session, api_key, domain, email, record_type, zone, proxied,
        timeout, ttl)

    if not result:
        return False

    @asyncio.coroutine
    def update_domain_interval(now):
        """Update the Cloudflare entry."""
        yield from _update_cloudflare(
            hass, session, api_key, domain, email, record_type, zone, proxied,
            timeout, ttl)

    hass.helpers.event.async_track_time_interval(
        update_domain_interval, timedelta(seconds=scan_interval))

    return True


@asyncio.coroutine
def _get_ip(session):
    """Get current IP address."""
    servers = [
        'https://diagnostic.opendns.com/myip',
        'https://icanhazip.com/',
        'http://checkip.amazonaws.com/',
    ]
    random.shuffle(servers)

    ip = None
    for server in servers:
        resp = yield from session.get(server)
        body = yield from resp.text()
        if resp.status == HTTP_OK:
            ip = body
            break
        else:
            continue

    if ip is None:
        _LOGGER.warning('Unable to identify current IP address')
    return ip


@asyncio.coroutine
def _get_record_identifier(session, zone, headers, domain):
    """Fetch Cloudflare identifier associated with domain."""
    url = API_BASE_URL.format(zone)

    params = {
        'name': domain,
    }

    resp = yield from session.get(url, params=params, headers=headers)
    resp_json = yield from resp.json()

    is_success = resp_json['success']
    record_count = resp_json['result_info']['count']

    if is_success and record_count == 1:
        identifier = resp_json['result'][0]['id']
    else:
        _LOGGER.warning('Could not fetch identifier for %s: %s',
                        domain, resp_json['errors'])
        identifier = None

    return identifier


@asyncio.coroutine
def _update_cloudflare(hass, session, api_key, domain, email, record_type,
                       zone, proxied, timeout, ttl):
    """Update Cloudflare."""
    headers = {
        "X-Auth-Email": email,
        "X-Auth-Key": api_key,
        "Content-Type": "application/json",
    }

    identifier = yield from _get_record_identifier(session, zone, headers,
                                                   domain)
    ip = yield from _get_ip(session)

    if identifier is None or ip is None:
        updated = False

    url = UPDATE_URL.format(zone, identifier)
    payload = {
        'type': record_type,
        'name': domain,
        'content': ip,
        'ttl': ttl,
        'proxied': proxied,
    }
    data = json.dumps(payload)

    try:
        with async_timeout.timeout(timeout, loop=hass.loop):
            resp = yield from session.put(url, data=data, headers=headers)
            resp_json = yield from resp.json()

            if resp_json['success'] is True:
                updated = True
            else:
                _LOGGER.warning('Updating Cloudflare failed: %s => %s',
                                domain, resp_json['errors'])
                updated = False

    except aiohttp.ClientError:
        _LOGGER.warning("Can't connect to Cloudflare API")
        updated = False

    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout from Cloudflare API for domain: %s",
                        domain)
        updated = False

    return updated
