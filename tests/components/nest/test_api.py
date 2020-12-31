"""Tests for the Nest integration API glue library."""

import time

from homeassistant.components.nest.api import AsyncConfigEntryAuth
from homeassistant.components.nest.const import (
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    SDM_SCOPES,
)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.util import dt

from tests.common import MockConfigEntry

DOMAIN = "nest"

CLIENT_ID = "some-client-id"
CLIENT_SECRET = "some-client-secret"

FAKE_TOKEN = "some-token"
FAKE_UPDATED_TOKEN = "some-updated-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"

EXPIRATION_TIME = time.time() + 86400

CONFIG_ENTRY_DATA = {
    "sdm": {},  # Indicates new SDM API, not legacy API
    "auth_implementation": "local",
    "token": {
        "access_token": FAKE_TOKEN,
        "expires_in": 12354,  # ignored
        "refresh_token": FAKE_REFRESH_TOKEN,
        "scope": " ".join(SDM_SCOPES),
        "token_type": "Bearer",
        "expires_at": EXPIRATION_TIME,
    },
}


def create_auth(hass, aioclient_mock, config_entry_data):
    """Create an AsyncConfigEntryAuth for tests."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA)
    config_entry.add_to_hass(hass)
    implementation = config_entry_oauth2_flow.LocalOAuth2Implementation(
        hass, DOMAIN, CLIENT_ID, CLIENT_SECRET, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, implementation)
    return AsyncConfigEntryAuth(aioclient_mock, session, CLIENT_ID, CLIENT_SECRET)


async def test_get_access_token(hass, aioclient_mock):
    """Verify that the access token is loaded from the ConfigEntry."""
    auth = create_auth(hass, aioclient_mock, CONFIG_ENTRY_DATA)

    token = await auth.async_get_access_token()
    assert token == FAKE_TOKEN


async def test_get_creds(hass, aioclient_mock):
    """Verify that the Credentials are created properly."""
    auth = create_auth(hass, aioclient_mock, CONFIG_ENTRY_DATA)

    creds = await auth.async_get_creds()
    assert creds.token == FAKE_TOKEN
    assert creds.refresh_token == FAKE_REFRESH_TOKEN
    assert int(dt.as_timestamp(creds.expiry)) == int(EXPIRATION_TIME)
    assert creds.valid
    assert not creds.expired
    assert creds.token_uri == OAUTH2_TOKEN
    assert creds.client_id == "some-client-id"
    assert creds.client_secret == "some-client-secret"
    assert creds.scopes == SDM_SCOPES


async def test_get_access_token_is_refreshed(hass, aioclient_mock):
    """Verify that an expired access token is refreshed when accessed."""
    data = CONFIG_ENTRY_DATA
    data["token"]["expires_at"] = time.time() - 86400
    auth = create_auth(hass, aioclient_mock, data)

    aioclient_mock.post(OAUTH2_TOKEN, json={"access_token": FAKE_UPDATED_TOKEN})

    token = await auth.async_get_access_token()
    assert token == FAKE_UPDATED_TOKEN


async def test_get_creds_is_expired(hass, aioclient_mock):
    """Verify that Credentials objects are properly created when expired."""
    expiration_time = time.time() - 86400
    data = CONFIG_ENTRY_DATA
    data["token"]["expires_at"] = expiration_time
    auth = create_auth(hass, aioclient_mock, data)

    # This credential is not refreshed (Pub/sub subscriber handles this).
    # Assert that it is still expired.
    creds = await auth.async_get_creds()
    assert creds.token == FAKE_TOKEN
    assert creds.refresh_token == FAKE_REFRESH_TOKEN
    assert int(dt.as_timestamp(creds.expiry)) == int(expiration_time)
    assert not creds.valid
    assert creds.expired
    assert creds.token_uri == OAUTH2_TOKEN
    assert creds.client_id == CLIENT_ID
    assert creds.client_secret == CLIENT_SECRET
    assert creds.scopes == SDM_SCOPES
