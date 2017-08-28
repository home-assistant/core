import asyncio
from datetime import timedelta
import json
import logging
import os
from urllib.parse import urljoin

import aiohttp
import async_timeout

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.dt import utcnow

from .const import AUTH_FILE, REQUEST_TIMEOUT, SERVERS

_LOGGER = logging.getLogger(__name__)


URL_CREATE_TOKEN = 'o/token/'
URL_REVOKE_TOKEN = 'o/revoke_token/'


class CloudError(Exception):
    """Base class for cloud related errors."""

    def __init__(self, reason=None, status=None):
        super().__init__(reason)
        self.status = status


class Unauthenticated(CloudError):
    """Raised when authentication failed."""


class UnknownError(CloudError):
    """Raised when an unknown error occurred."""


@asyncio.coroutine
def async_load_auth(hass, mode):
    """Load authentication from disk and verify it."""
    auth = yield from hass.async_add_job(_read_auth, hass, mode)

    if not auth:
        return None

    cloud = Cloud(hass, mode, auth)

    try:
        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            auth_check = yield from cloud.async_refresh_account_info()

            if not auth_check:
                _LOGGER.error('Unable to validate credentials.')
                return None

            return cloud

    except asyncio.TimeoutErrror:
        _LOGGER.error('Unable to reach server to validate credentials.')
        return None


@asyncio.coroutine
def async_login(hass, mode, username, password, scope=None):
    """Get a token using a username and password.

    Returns a coroutine.
    """
    data = {
        'grant_type': 'password',
        'username': username,
        'password': password
    }
    if scope is not None:
        data['scope'] = scope

    auth = yield from _async_get_token(hass, data)
    return Cloud(hass, mode, auth)


@asyncio.coroutine
def _async_get_token(hass, mode, data):
    """Get a new token and return it as a dictionary.

    Raises exceptions when errors occur:
     - Unauthenticated
     - UnknownError
    """
    session = async_get_clientsession(hass)
    auth = aiohttp.BasicAuth(*_client_credentials(mode))

    try:
        req = yield from session.post(
            _url(mode, URL_CREATE_TOKEN),
            data=data,
            auth=auth
        )

        if req.status in (401, 403):
            _LOGGER.error('Cloud login failed: %d', req.status)
            raise Unauthenticated(status=req.status)
        elif req.status != 200:
            _LOGGER.error('Cloud login failed: %d', req.status)
            raise UnknownError(status=req.status)

        response = yield from req.json(content_type=None)
        data['expires_at'] = \
            (utcnow() + timedelta(seconds=data['expires_in'])).isoformat()

        return response

    except aiohttp.ClientError:
        raise UnknownError()


class Cloud:
    """Store Hass Cloud info."""

    def __init__(self, hass, mode, auth):
        """Initialize Hass cloud info object."""
        self.hass = hass
        self.mode = mode
        self.auth = auth
        self.account = None

    @property
    def access_token(self):
        """Return access token."""
        return self.auth['access_token']

    @property
    def refresh_token(self):
        """Get refresh token."""
        return self.auth['refresh_token']

    @asyncio.coroutine
    def async_refresh_account_info(self):
        req = yield from self.async_request(
            self.hass, 'get', 'account.json')

        if req.status != 200:
            return False

        self.account = yield from req.json()
        return True

    @asyncio.coroutine
    def async_refresh_access_token(self):
        """Get a token using a refresh token."""
        try:
            self.auth = yield from _async_get_token(self.hass, {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
            })

            yield from self.hass.async_add_job(
                _write_auth, self.hass, self.auth)

            return True
        except CloudError:
            return False

    @asyncio.coroutine
    def async_revoke_access_token(self):
        """Revoke active access token."""
        session = async_get_clientsession(self.hass)
        client_id, client_secret = _client_credentials(self.mode)
        data = {
            'token': self.access_token,
            'client_id': client_id,
            'client_secret': client_secret
        }
        try:
            req = yield from session.post(
                _url(self.mode, URL_REVOKE_TOKEN),
                data=data,
            )

            if req.status != 200:
                _LOGGER.error('Cloud logout failed: %d', req.status)
                raise UnknownError(status=req.status)

            yield from self.hass.async_add_job(
                _write_auth, self.hass, self.mode, None)

        except aiohttp.ClientError as err:
            raise UnknownError()

    @asyncio.coroutine
    def async_request(self, method, path, **kwargs):
        """Make a request to Home Assistant cloud.

        Will refresh the token if necessary."""
        session = async_get_clientsession(self.hass)
        url = _url(self.mode, path)

        if 'headers' not in kwargs:
            kwargs['headers'] = {}

        kwargs['headers']['authorization'] = \
            'Bearer {}'.format(self.access_token)

        request = yield from session.request(method, url, **kwargs)

        if request.status != 403:
            return request

        # Maybe token expired. Try refreshing it.
        reauth = yield from self.async_refresh_access_token()

        if not reauth:
            return request

        # Release old connection back to the pool.
        yield from request.release()

        kwargs['headers']['authorization'] = \
            'Bearer {}'.format(self.access_token)

        # If we are not already fetching the account info,
        # refresh the account info.
        if path != URL_CREATE_TOKEN:
            yield from self.async_refresh_account_info()

        request = yield from session.request(method, url, **kwargs)

        return request


def _read_auth(hass, mode):
    """Read auth file."""
    path = hass.config.path(AUTH_FILE)

    if not os.path.isfile(path):
        return None

    with open(path) as fp:
        return json.load(fp).get(mode)


def _write_auth(hass, mode, data):
    """Write auth info for specified mode.

    Pass in None for data to remove authentication for that mode.
    """
    content = _read_auth(hass, mode) or {}

    if data is None:
        content.pop(mode, None)
    else:
        content[mode] = data

    with open(hass.config.path(AUTH_FILE), 'wt') as file:
        file.write(json.dumps(content))


def _client_credentials(mode):
    """Get the client credentials.

    Async friendly.
    """
    if mode not in SERVERS:
        raise ValueError('Mode {} is not supported.'.format(mode))

    return SERVERS[mode]['client_id'], SERVERS[mode]['client_secret']


def _url(mode, path):
    """Generate a url for the cloud.

    Async friendly.
    """
    if mode not in SERVERS:
        raise ValueError('Mode {} is not supported.'.format(mode))

    return urljoin(SERVERS[mode]['host'], path)
