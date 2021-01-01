"""Tests for the Nest integration API glue library."""

import time

from google_nest_sdm.google_nest_subscriber import (
    AbstractSubscriberFactory,
    GoogleNestSubscriber,
)

from homeassistant.components.nest.api import AsyncConfigEntryAuth
from homeassistant.components.nest.const import OAUTH2_TOKEN, SDM_SCOPES
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.util import dt

from tests.async_mock import MagicMock, PropertyMock

DOMAIN = "nest"

CLIENT_ID = "some-client-id"
CLIENT_SECRET = "some-client-secret"

FAKE_TOKEN = "some-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"

PROJECT_ID = "project-id"
SUBSCRIBER_ID = "projects/example/subscriptions/example"


class FakeSubscriberFactory(AbstractSubscriberFactory):
    """Fake subscriber for capturing credentials."""

    def __init__(self):
        """Initialize FakeSubscriberFactory."""
        self.creds = None

    async def async_new_subscriber(
        self, creds, subscription_name, loop, async_callback
    ):
        """Capture credentials for tests."""
        self.creds = creds
        return None


async def test_get_access_token(hass, aioclient_mock, session):
    """Verify that the access token is loaded from the ConfigEntry."""
    session = MagicMock(config_entry_oauth2_flow.OAuth2Session)
    type(session).valid_token = PropertyMock(return_value=True)
    type(session).token = PropertyMock(
        return_value={
            "access_token": FAKE_TOKEN,
        }
    )

    auth = AsyncConfigEntryAuth(aioclient_mock, session, CLIENT_ID, CLIENT_SECRET)

    token = await auth.async_get_access_token()
    assert len(session.async_ensure_token_valid.mock_calls) == 0
    assert token == FAKE_TOKEN


async def test_get_creds(hass, aioclient_mock):
    """Verify that the Credentials are created properly."""
    expiration_time = time.time() + 86400
    session = MagicMock(config_entry_oauth2_flow.OAuth2Session)
    type(session).token = PropertyMock(
        return_value={
            "access_token": FAKE_TOKEN,
            "refresh_token": FAKE_REFRESH_TOKEN,
            "expires_at": expiration_time,
        }
    )
    auth = AsyncConfigEntryAuth(aioclient_mock, session, CLIENT_ID, CLIENT_SECRET)

    subscriber_factory = FakeSubscriberFactory()
    subscriber = GoogleNestSubscriber(
        auth, PROJECT_ID, SUBSCRIBER_ID, subscriber_factory
    )
    await subscriber.start_async()

    creds = subscriber_factory.creds
    assert creds.token == FAKE_TOKEN
    assert creds.refresh_token == FAKE_REFRESH_TOKEN
    assert int(dt.as_timestamp(creds.expiry)) == int(expiration_time)
    assert creds.valid
    assert not creds.expired
    assert creds.token_uri == OAUTH2_TOKEN
    assert creds.client_id == "some-client-id"
    assert creds.client_secret == "some-client-secret"
    assert creds.scopes == SDM_SCOPES


async def test_get_access_token_is_refreshed(hass, aioclient_mock):
    """Verify that an expired access token is refreshed when accessed."""
    session = MagicMock(config_entry_oauth2_flow.OAuth2Session)
    type(session).valid_token = PropertyMock(return_value=False)
    type(session).token = PropertyMock(
        return_value={
            "access_token": FAKE_TOKEN,
        }
    )
    auth = AsyncConfigEntryAuth(aioclient_mock, session, CLIENT_ID, CLIENT_SECRET)
    token = await auth.async_get_access_token()
    assert len(session.async_ensure_token_valid.mock_calls) == 1
    assert token == FAKE_TOKEN


async def test_get_creds_is_expired(hass, aioclient_mock):
    """Verify that Credentials objects are properly created when expired."""
    expiration_time = time.time() - 86400
    session = MagicMock(config_entry_oauth2_flow.OAuth2Session)
    type(session).token = PropertyMock(
        return_value={
            "access_token": FAKE_TOKEN,
            "refresh_token": FAKE_REFRESH_TOKEN,
            "expires_at": expiration_time,
        }
    )
    auth = AsyncConfigEntryAuth(aioclient_mock, session, CLIENT_ID, CLIENT_SECRET)

    subscriber_factory = FakeSubscriberFactory()
    subscriber = GoogleNestSubscriber(
        auth, PROJECT_ID, SUBSCRIBER_ID, subscriber_factory
    )
    await subscriber.start_async()

    # This credential is not refreshed (Pub/sub subscriber handles this).
    # Assert that it is still expired.
    creds = subscriber_factory.creds
    assert creds.token == FAKE_TOKEN
    assert creds.refresh_token == FAKE_REFRESH_TOKEN
    assert int(dt.as_timestamp(creds.expiry)) == int(expiration_time)
    assert not creds.valid
    assert creds.expired
    assert creds.token_uri == OAUTH2_TOKEN
    assert creds.client_id == CLIENT_ID
    assert creds.client_secret == CLIENT_SECRET
    assert creds.scopes == SDM_SCOPES
