"""Test the Google Nest Device Access config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries, setup
from homeassistant.components.nest.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
PROJECT_ID = "project-id-4321"
SUBSCRIBER_ID = "projects/example/subscriptions/subscriber-id-9876"

CONFIG = {
    DOMAIN: {
        "project_id": PROJECT_ID,
        "subscriber_id": SUBSCRIBER_ID,
        CONF_CLIENT_ID: CLIENT_ID,
        CONF_CLIENT_SECRET: CLIENT_SECRET,
    },
    "http": {"base_url": "https://example.com"},
}

ORIG_AUTH_DOMAIN = DOMAIN
WEB_AUTH_DOMAIN = DOMAIN
APP_AUTH_DOMAIN = f"{DOMAIN}.installed"
WEB_REDIRECT_URL = "https://example.com/auth/external/callback"
APP_REDIRECT_URL = "urn:ietf:wg:oauth:2.0:oob"


def get_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Return a single config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    return entries[0]


def create_config_entry(hass: HomeAssistant, data: dict) -> ConfigEntry:
    """Create the ConfigEntry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)
    return entry


class OAuthFixture:
    """Simulate the oauth flow used by the config flow."""

    def __init__(self, hass, hass_client_no_auth, aioclient_mock):
        """Initialize OAuthFixture."""
        self.hass = hass
        self.hass_client = hass_client_no_auth
        self.aioclient_mock = aioclient_mock

    async def async_pick_flow(self, result: dict, auth_domain: str) -> dict:
        """Invoke flow to puth the auth type to use for this flow."""
        assert result["type"] == "form"
        assert result["step_id"] == "pick_implementation"

        return await self.hass.config_entries.flow.async_configure(
            result["flow_id"], {"implementation": auth_domain}
        )

    async def async_oauth_web_flow(self, result: dict) -> ConfigEntry:
        """Invoke the oauth flow for Web Auth with fake responses."""
        state = self.create_state(result, WEB_REDIRECT_URL)
        assert result["url"] == self.authorize_url(state, WEB_REDIRECT_URL)

        # Simulate user redirect back with auth code
        client = await self.hass_client()
        resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
        assert resp.status == 200
        assert resp.headers["content-type"] == "text/html; charset=utf-8"

        return await self.async_finish_flow(result)

    async def async_oauth_app_flow(self, result: dict) -> ConfigEntry:
        """Invoke the oauth flow for Installed Auth with fake responses."""
        # Render form with a link to get an auth token
        assert result["type"] == "form"
        assert result["step_id"] == "auth"
        assert "description_placeholders" in result
        assert "url" in result["description_placeholders"]
        state = self.create_state(result, APP_REDIRECT_URL)
        assert result["description_placeholders"]["url"] == self.authorize_url(
            state, APP_REDIRECT_URL
        )
        # Simulate user entering auth token in form
        return await self.async_finish_flow(result, {"code": "abcd"})

    def create_state(self, result: dict, redirect_url: str) -> str:
        """Create state object based on redirect url."""
        return config_entry_oauth2_flow._encode_jwt(
            self.hass,
            {
                "flow_id": result["flow_id"],
                "redirect_uri": redirect_url,
            },
        )

    def authorize_url(self, state: str, redirect_url: str) -> str:
        """Generate the expected authorization url."""
        oauth_authorize = OAUTH2_AUTHORIZE.format(project_id=PROJECT_ID)
        return (
            f"{oauth_authorize}?response_type=code&client_id={CLIENT_ID}"
            f"&redirect_uri={redirect_url}"
            f"&state={state}&scope=https://www.googleapis.com/auth/sdm.service"
            "+https://www.googleapis.com/auth/pubsub"
            "&access_type=offline&prompt=consent"
        )

    async def async_finish_flow(self, result, user_input: dict = None) -> ConfigEntry:
        """Finish the OAuth flow exchanging auth token for refresh token."""
        self.aioclient_mock.post(
            OAUTH2_TOKEN,
            json={
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
            },
        )

        with patch(
            "homeassistant.components.nest.async_setup_entry", return_value=True
        ) as mock_setup:
            await self.hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            assert len(mock_setup.mock_calls) == 1
            await self.hass.async_block_till_done()

        return get_config_entry(self.hass)


@pytest.fixture
async def oauth(hass, hass_client_no_auth, aioclient_mock, current_request_with_host):
    """Create the simulated oauth flow."""
    return OAuthFixture(hass, hass_client_no_auth, aioclient_mock)


async def test_web_full_flow(hass, oauth):
    """Check full flow."""
    assert await setup.async_setup_component(hass, DOMAIN, CONFIG)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await oauth.async_pick_flow(result, WEB_AUTH_DOMAIN)

    entry = await oauth.async_oauth_web_flow(result)
    assert entry.title == "OAuth for Web"
    assert "token" in entry.data
    entry.data["token"].pop("expires_at")
    assert entry.unique_id == DOMAIN
    assert entry.data["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }


async def test_web_reauth(hass, oauth):
    """Test Nest reauthentication."""

    assert await setup.async_setup_component(hass, DOMAIN, CONFIG)

    old_entry = create_config_entry(
        hass,
        {
            "auth_implementation": WEB_AUTH_DOMAIN,
            "token": {
                # Verify this is replaced at end of the test
                "access_token": "some-revoked-token",
            },
            "sdm": {},
        },
    )

    entry = get_config_entry(hass)
    assert entry.data["token"] == {
        "access_token": "some-revoked-token",
    }

    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data=old_entry.data
    )

    # Advance through the reauth flow
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    # Run the oauth flow
    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})

    entry = await oauth.async_oauth_web_flow(result)
    # Verify existing tokens are replaced
    entry.data["token"].pop("expires_at")
    assert entry.unique_id == DOMAIN
    assert entry.data["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }
    assert entry.data["auth_implementation"] == WEB_AUTH_DOMAIN


async def test_single_config_entry(hass):
    """Test that only a single config entry is allowed."""
    create_config_entry(hass, {"auth_implementation": WEB_AUTH_DOMAIN, "sdm": {}})

    assert await setup.async_setup_component(hass, DOMAIN, CONFIG)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_unexpected_existing_config_entries(hass, oauth):
    """Test Nest reauthentication with multiple existing config entries."""
    # Note that this case will not happen in the future since only a single
    # instance is now allowed, but this may have been allowed in the past.
    # On reauth, only one entry is kept and the others are deleted.

    assert await setup.async_setup_component(hass, DOMAIN, CONFIG)

    old_entry = MockConfigEntry(
        domain=DOMAIN, data={"auth_implementation": WEB_AUTH_DOMAIN, "sdm": {}}
    )
    old_entry.add_to_hass(hass)

    old_entry = MockConfigEntry(
        domain=DOMAIN, data={"auth_implementation": WEB_AUTH_DOMAIN, "sdm": {}}
    )
    old_entry.add_to_hass(hass)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2

    # Invoke the reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data=old_entry.data
    )
    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    flows = hass.config_entries.flow.async_progress()

    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})
    await oauth.async_oauth_web_flow(result)

    # Only a single entry now exists, and the other was cleaned up
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.unique_id == DOMAIN
    entry.data["token"].pop("expires_at")
    assert entry.data["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }


async def test_app_full_flow(hass, oauth, aioclient_mock):
    """Check full flow."""
    assert await setup.async_setup_component(hass, DOMAIN, CONFIG)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)

    entry = await oauth.async_oauth_app_flow(result)
    assert entry.title == "OAuth for Apps"
    assert "token" in entry.data
    entry.data["token"].pop("expires_at")
    assert entry.unique_id == DOMAIN
    assert entry.data["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }


async def test_app_reauth(hass, oauth):
    """Test Nest reauthentication for Installed App Auth."""

    assert await setup.async_setup_component(hass, DOMAIN, CONFIG)

    old_entry = create_config_entry(
        hass,
        {
            "auth_implementation": APP_AUTH_DOMAIN,
            "token": {
                # Verify this is replaced at end of the test
                "access_token": "some-revoked-token",
            },
            "sdm": {},
        },
    )

    entry = get_config_entry(hass)
    assert entry.data["token"] == {
        "access_token": "some-revoked-token",
    }

    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data=old_entry.data
    )

    # Advance through the reauth flow
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    # Run the oauth flow
    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})
    await oauth.async_oauth_app_flow(result)

    # Verify existing tokens are replaced
    entry = get_config_entry(hass)
    entry.data["token"].pop("expires_at")
    assert entry.unique_id == DOMAIN
    assert entry.data["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }
    assert entry.data["auth_implementation"] == APP_AUTH_DOMAIN
