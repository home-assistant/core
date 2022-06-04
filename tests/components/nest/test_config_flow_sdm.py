"""Test the Google Nest Device Access config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from google_nest_sdm.exceptions import (
    AuthException,
    ConfigurationException,
    SubscriberException,
)
from google_nest_sdm.structure import Structure
import pytest

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.nest.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_entry_oauth2_flow

from .common import (
    APP_AUTH_DOMAIN,
    CLIENT_ID,
    CLOUD_PROJECT_ID,
    FAKE_TOKEN,
    PROJECT_ID,
    SUBSCRIBER_ID,
    TEST_CONFIG_HYBRID,
    TEST_CONFIG_YAML_ONLY,
    TEST_CONFIGFLOW_APP_CREDS,
    TEST_CONFIGFLOW_HYBRID,
    TEST_CONFIGFLOW_YAML_ONLY,
    WEB_AUTH_DOMAIN,
    MockConfigEntry,
    NestTestConfig,
)

WEB_REDIRECT_URL = "https://example.com/auth/external/callback"
APP_REDIRECT_URL = "urn:ietf:wg:oauth:2.0:oob"


FAKE_DHCP_DATA = dhcp.DhcpServiceInfo(
    ip="127.0.0.2", macaddress="00:11:22:33:44:55", hostname="fake_hostname"
)


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

        return await self.async_configure(result, {"implementation": auth_domain})

    async def async_oauth_web_flow(self, result: dict, project_id=PROJECT_ID) -> None:
        """Invoke the oauth flow for Web Auth with fake responses."""
        state = self.create_state(result, WEB_REDIRECT_URL)
        assert result["type"] == "external"
        assert result["url"] == self.authorize_url(
            state,
            WEB_REDIRECT_URL,
            CLIENT_ID,
            project_id,
        )

        # Simulate user redirect back with auth code
        client = await self.hass_client()
        resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
        assert resp.status == 200
        assert resp.headers["content-type"] == "text/html; charset=utf-8"

        await self.async_mock_refresh(result)

    async def async_oauth_app_flow(
        self, result: dict, client_id: str = CLIENT_ID, project_id: str = PROJECT_ID
    ) -> None:
        """Invoke the oauth flow for Installed Auth with fake responses."""
        # Render form with a link to get an auth token
        assert result["type"] == "form"
        assert result["step_id"] == "auth"
        assert "description_placeholders" in result
        assert "url" in result["description_placeholders"]
        state = self.create_state(result, APP_REDIRECT_URL)
        assert result["description_placeholders"]["url"] == self.authorize_url(
            state,
            APP_REDIRECT_URL,
            client_id,
            project_id,
        )
        # Simulate user entering auth token in form
        await self.async_mock_refresh(result, {"code": "abcd"})

    async def async_reauth(self, old_data: dict) -> dict:
        """Initiate a reuath flow."""
        result = await self.hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data=old_data
        )
        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"

        # Advance through the reauth flow
        flows = self.hass.config_entries.flow.async_progress()
        assert len(flows) == 1
        assert flows[0]["step_id"] == "reauth_confirm"

        # Advance to the oauth flow
        return await self.hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {}
        )

    def create_state(self, result: dict, redirect_url: str) -> str:
        """Create state object based on redirect url."""
        return config_entry_oauth2_flow._encode_jwt(
            self.hass,
            {
                "flow_id": result["flow_id"],
                "redirect_uri": redirect_url,
            },
        )

    def authorize_url(
        self, state: str, redirect_url: str, client_id: str, project_id: str
    ) -> str:
        """Generate the expected authorization url."""
        oauth_authorize = OAUTH2_AUTHORIZE.format(project_id=project_id)
        return (
            f"{oauth_authorize}?response_type=code&client_id={client_id}"
            f"&redirect_uri={redirect_url}"
            f"&state={state}&scope=https://www.googleapis.com/auth/sdm.service"
            "+https://www.googleapis.com/auth/pubsub"
            "&access_type=offline&prompt=consent"
        )

    async def async_mock_refresh(self, result, user_input: dict = None) -> None:
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

    async def async_finish_setup(
        self, result: dict, user_input: dict = None
    ) -> ConfigEntry:
        """Finish the OAuth flow exchanging auth token for refresh token."""
        with patch(
            "homeassistant.components.nest.async_setup_entry", return_value=True
        ) as mock_setup:
            await self.async_configure(result, user_input)
            assert len(mock_setup.mock_calls) == 1
            await self.hass.async_block_till_done()
        return self.get_config_entry()

    async def async_configure(
        self, result: dict[str, Any], user_input: dict[str, Any]
    ) -> dict:
        """Advance to the next step in the config flow."""
        return await self.hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input,
        )

    async def async_pubsub_flow(self, result: dict, cloud_project_id="") -> None:
        """Verify the pubsub creation step."""
        # Render form with a link to get an auth token
        assert result["type"] == "form"
        assert result["step_id"] == "pubsub"
        assert "description_placeholders" in result
        assert "url" in result["description_placeholders"]
        assert result["data_schema"]({}) == {"cloud_project_id": cloud_project_id}

    def get_config_entry(self) -> ConfigEntry:
        """Get the config entry."""
        entries = self.hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        return entries[0]


@pytest.fixture
async def oauth(hass, hass_client_no_auth, aioclient_mock, current_request_with_host):
    """Create the simulated oauth flow."""
    return OAuthFixture(hass, hass_client_no_auth, aioclient_mock)


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_APP_CREDS])
async def test_app_credentials(hass, oauth, subscriber, setup_platform):
    """Check full flow."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "form"
    assert result.get("step_id") == "cloud_project"

    result = await oauth.async_configure(result, {"cloud_project_id": CLOUD_PROJECT_ID})
    assert result.get("type") == "form"
    assert result.get("step_id") == "device_project"

    result = await oauth.async_configure(result, {"project_id": PROJECT_ID})
    await oauth.async_oauth_web_flow(result)

    entry = await oauth.async_finish_setup(result)

    data = dict(entry.data)
    assert "token" in data
    data["token"].pop("expires_in")
    data["token"].pop("expires_at")
    assert "subscriber_id" in data
    assert f"projects/{CLOUD_PROJECT_ID}/subscriptions" in data["subscriber_id"]
    data.pop("subscriber_id")
    assert data == {
        "sdm": {},
        "auth_implementation": "imported-cred",
        "cloud_project_id": CLOUD_PROJECT_ID,
        "project_id": PROJECT_ID,
        "token": {
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
        },
    }


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_APP_CREDS])
async def test_config_flow_restart(hass, oauth, subscriber, setup_platform):
    """Check with auth implementation is re-initialized when aborting the flow."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "form"
    assert result.get("step_id") == "cloud_project"

    result = await oauth.async_configure(result, {"cloud_project_id": CLOUD_PROJECT_ID})
    assert result.get("type") == "form"
    assert result.get("step_id") == "device_project"

    result = await oauth.async_configure(result, {"project_id": PROJECT_ID})
    await oauth.async_oauth_web_flow(result)

    # At this point, we should have a valid auth implementation configured.
    # Simulate aborting the flow and starting over to ensure we get prompted
    # again to configure everything.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "form"
    assert result.get("step_id") == "cloud_project"

    # Change the values to show they are reflected below
    result = await oauth.async_configure(
        result, {"cloud_project_id": "new-cloud-project-id"}
    )
    assert result.get("type") == "form"
    assert result.get("step_id") == "device_project"

    result = await oauth.async_configure(result, {"project_id": "new-project-id"})
    await oauth.async_oauth_web_flow(result, "new-project-id")

    entry = await oauth.async_finish_setup(result, {"code": "1234"})

    data = dict(entry.data)
    assert "token" in data
    data["token"].pop("expires_in")
    data["token"].pop("expires_at")
    assert "subscriber_id" in data
    assert "projects/new-cloud-project-id/subscriptions" in data["subscriber_id"]
    data.pop("subscriber_id")
    assert data == {
        "sdm": {},
        "auth_implementation": "imported-cred",
        "cloud_project_id": "new-cloud-project-id",
        "project_id": "new-project-id",
        "token": {
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
        },
    }


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_APP_CREDS])
async def test_config_flow_wrong_project_id(hass, oauth, subscriber, setup_platform):
    """Check the case where the wrong project ids are entered."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "form"
    assert result.get("step_id") == "cloud_project"

    result = await oauth.async_configure(result, {"cloud_project_id": CLOUD_PROJECT_ID})
    assert result.get("type") == "form"
    assert result.get("step_id") == "device_project"

    # Enter the cloud project id instead of device access project id (really we just check
    # they are the same value which is never correct)
    result = await oauth.async_configure(result, {"project_id": CLOUD_PROJECT_ID})
    assert result["type"] == "form"
    assert "errors" in result
    assert "project_id" in result["errors"]
    assert result["errors"]["project_id"] == "wrong_project_id"

    # Fix with a correct value and complete the rest of the flow
    result = await oauth.async_configure(result, {"project_id": PROJECT_ID})
    await oauth.async_oauth_web_flow(result)
    await hass.async_block_till_done()

    entry = await oauth.async_finish_setup(result, {"code": "1234"})

    data = dict(entry.data)
    assert "token" in data
    data["token"].pop("expires_in")
    data["token"].pop("expires_at")
    assert "subscriber_id" in data
    assert f"projects/{CLOUD_PROJECT_ID}/subscriptions" in data["subscriber_id"]
    data.pop("subscriber_id")
    assert data == {
        "sdm": {},
        "auth_implementation": "imported-cred",
        "cloud_project_id": CLOUD_PROJECT_ID,
        "project_id": PROJECT_ID,
        "token": {
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
        },
    }


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_APP_CREDS])
async def test_config_flow_pubsub_configuration_error(
    hass,
    oauth,
    setup_platform,
    mock_subscriber,
):
    """Check full flow fails with configuration error."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "form"
    assert result.get("step_id") == "cloud_project"

    result = await oauth.async_configure(result, {"cloud_project_id": CLOUD_PROJECT_ID})
    assert result.get("type") == "form"
    assert result.get("step_id") == "device_project"

    result = await oauth.async_configure(result, {"project_id": PROJECT_ID})
    await oauth.async_oauth_web_flow(result)

    mock_subscriber.create_subscription.side_effect = ConfigurationException
    result = await oauth.async_configure(result, {"code": "1234"})

    assert result["type"] == "form"
    assert "errors" in result
    assert "cloud_project_id" in result["errors"]
    assert result["errors"]["cloud_project_id"] == "bad_project_id"


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_APP_CREDS])
async def test_config_flow_pubsub_subscriber_error(
    hass, oauth, setup_platform, mock_subscriber
):
    """Check full flow with a subscriber error."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "form"
    assert result.get("step_id") == "cloud_project"

    result = await oauth.async_configure(result, {"cloud_project_id": CLOUD_PROJECT_ID})
    assert result.get("type") == "form"
    assert result.get("step_id") == "device_project"

    result = await oauth.async_configure(result, {"project_id": PROJECT_ID})
    await oauth.async_oauth_web_flow(result)

    mock_subscriber.create_subscription.side_effect = SubscriberException()
    result = await oauth.async_configure(result, {"code": "1234"})

    assert result["type"] == "form"
    assert "errors" in result
    assert "cloud_project_id" in result["errors"]
    assert result["errors"]["cloud_project_id"] == "subscriber_error"


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_YAML_ONLY])
async def test_web_full_flow(hass, oauth, setup_platform):
    """Check full flow."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await oauth.async_pick_flow(result, WEB_AUTH_DOMAIN)

    await oauth.async_oauth_web_flow(result)
    entry = await oauth.async_finish_setup(result)
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
    # Subscriber from configuration.yaml
    assert "subscriber_id" not in entry.data


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIG_YAML_ONLY])
async def test_web_reauth(hass, oauth, setup_platform, config_entry):
    """Test Nest reauthentication."""
    await setup_platform()

    assert config_entry.data["token"].get("access_token") == FAKE_TOKEN

    orig_subscriber_id = config_entry.data.get("subscriber_id")
    result = await oauth.async_reauth(config_entry.data)

    await oauth.async_oauth_web_flow(result)
    entry = await oauth.async_finish_setup(result)
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
    assert entry.data.get("subscriber_id") == orig_subscriber_id  # Not updated


async def test_single_config_entry(hass, setup_platform):
    """Test that only a single config entry is allowed."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_unexpected_existing_config_entries(
    hass, oauth, setup_platform, config_entry
):
    """Test Nest reauthentication with multiple existing config entries."""
    # Note that this case will not happen in the future since only a single
    # instance is now allowed, but this may have been allowed in the past.
    # On reauth, only one entry is kept and the others are deleted.

    await setup_platform()

    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_entry.data,
    )
    old_entry.add_to_hass(hass)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2

    orig_subscriber_id = config_entry.data.get("subscriber_id")

    # Invoke the reauth flow
    result = await oauth.async_reauth(old_entry.data)

    await oauth.async_oauth_web_flow(result)

    await oauth.async_finish_setup(result)

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
    assert entry.data.get("subscriber_id") == orig_subscriber_id  # Not updated


async def test_reauth_missing_config_entry(hass, setup_platform):
    """Test the reauth flow invoked missing existing data."""
    await setup_platform()

    # Invoke the reauth flow with no existing data
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data=None
    )
    assert result["type"] == "abort"
    assert result["reason"] == "missing_configuration"


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_YAML_ONLY])
async def test_app_full_flow(hass, oauth, setup_platform):
    """Check full flow."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)

    await oauth.async_oauth_app_flow(result)
    entry = await oauth.async_finish_setup(result, {"code": "1234"})
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
    # Subscriber from configuration.yaml
    assert "subscriber_id" not in entry.data


@pytest.mark.parametrize(
    "nest_test_config,auth_implementation", [(TEST_CONFIG_YAML_ONLY, APP_AUTH_DOMAIN)]
)
async def test_app_reauth(hass, oauth, setup_platform, config_entry):
    """Test Nest reauthentication for Installed App Auth."""

    await setup_platform()

    orig_subscriber_id = config_entry.data.get("subscriber_id")

    result = await oauth.async_reauth(config_entry.data)
    await oauth.async_oauth_app_flow(result)

    # Verify existing tokens are replaced
    entry = await oauth.async_finish_setup(result, {"code": "1234"})
    entry.data["token"].pop("expires_at")
    assert entry.unique_id == DOMAIN
    assert entry.data["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }
    assert entry.data["auth_implementation"] == APP_AUTH_DOMAIN
    assert entry.data.get("subscriber_id") == orig_subscriber_id  # Not updated


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_HYBRID])
async def test_pubsub_subscription(hass, oauth, subscriber, setup_platform):
    """Check flow that creates a pub/sub subscription."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)

    result = await oauth.async_configure(result, {"code": "1234"})
    await oauth.async_pubsub_flow(result)
    entry = await oauth.async_finish_setup(
        result, {"cloud_project_id": CLOUD_PROJECT_ID}
    )

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
    assert "subscriber_id" in entry.data
    assert entry.data["cloud_project_id"] == CLOUD_PROJECT_ID


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_HYBRID])
async def test_pubsub_subscription_strip_whitespace(
    hass, oauth, subscriber, setup_platform
):
    """Check that project id has whitespace stripped on entry."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)

    result = await oauth.async_configure(result, {"code": "1234"})
    await oauth.async_pubsub_flow(result)
    entry = await oauth.async_finish_setup(
        result, {"cloud_project_id": " " + CLOUD_PROJECT_ID + " "}
    )

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
    assert "subscriber_id" in entry.data
    assert entry.data["cloud_project_id"] == CLOUD_PROJECT_ID


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_HYBRID])
async def test_pubsub_subscription_auth_failure(
    hass, oauth, setup_platform, mock_subscriber
):
    """Check flow that creates a pub/sub subscription."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)
    result = await oauth.async_configure(result, {"code": "1234"})

    mock_subscriber.create_subscription.side_effect = AuthException()

    await oauth.async_pubsub_flow(result)
    result = await oauth.async_configure(result, {"cloud_project_id": CLOUD_PROJECT_ID})

    assert result["type"] == "abort"
    assert result["reason"] == "invalid_access_token"


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_HYBRID])
async def test_pubsub_subscription_failure(
    hass, oauth, setup_platform, mock_subscriber
):
    """Check flow that creates a pub/sub subscription."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)
    result = await oauth.async_configure(result, {"code": "1234"})
    await oauth.async_pubsub_flow(result)

    mock_subscriber.create_subscription.side_effect = SubscriberException()

    result = await oauth.async_configure(result, {"cloud_project_id": CLOUD_PROJECT_ID})

    assert result["type"] == "form"
    assert "errors" in result
    assert "cloud_project_id" in result["errors"]
    assert result["errors"]["cloud_project_id"] == "subscriber_error"


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_HYBRID])
async def test_pubsub_subscription_configuration_failure(
    hass, oauth, setup_platform, mock_subscriber
):
    """Check flow that creates a pub/sub subscription."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)
    result = await oauth.async_configure(result, {"code": "1234"})
    await oauth.async_pubsub_flow(result)

    mock_subscriber.create_subscription.side_effect = ConfigurationException()
    result = await oauth.async_configure(result, {"cloud_project_id": CLOUD_PROJECT_ID})

    assert result["type"] == "form"
    assert "errors" in result
    assert "cloud_project_id" in result["errors"]
    assert result["errors"]["cloud_project_id"] == "bad_project_id"


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_HYBRID])
async def test_pubsub_with_wrong_project_id(hass, oauth, setup_platform):
    """Test a possible common misconfiguration mixing up project ids."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)
    result = await oauth.async_configure(result, {"code": "1234"})
    await oauth.async_pubsub_flow(result)
    result = await oauth.async_configure(
        result, {"cloud_project_id": PROJECT_ID}  # SDM project id
    )
    await hass.async_block_till_done()

    assert result["type"] == "form"
    assert "errors" in result
    assert "cloud_project_id" in result["errors"]
    assert result["errors"]["cloud_project_id"] == "wrong_project_id"


@pytest.mark.parametrize(
    "nest_test_config,auth_implementation", [(TEST_CONFIG_HYBRID, APP_AUTH_DOMAIN)]
)
async def test_pubsub_subscriber_config_entry_reauth(
    hass, oauth, setup_platform, subscriber, config_entry
):
    """Test the pubsub subscriber id is preserved during reauth."""
    await setup_platform()

    result = await oauth.async_reauth(config_entry.data)
    await oauth.async_oauth_app_flow(result)

    # Entering an updated access token refreshs the config entry.
    entry = await oauth.async_finish_setup(result, {"code": "1234"})
    entry.data["token"].pop("expires_at")
    assert entry.unique_id == DOMAIN
    assert entry.data["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }
    assert entry.data["auth_implementation"] == APP_AUTH_DOMAIN
    assert entry.data["subscriber_id"] == SUBSCRIBER_ID
    assert entry.data["cloud_project_id"] == CLOUD_PROJECT_ID


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_HYBRID])
async def test_config_entry_title_from_home(hass, oauth, setup_platform, subscriber):
    """Test that the Google Home name is used for the config entry title."""

    device_manager = await subscriber.async_get_device_manager()
    device_manager.add_structure(
        Structure.MakeStructure(
            {
                "name": f"enterprise/{PROJECT_ID}/structures/some-structure-id",
                "traits": {
                    "sdm.structures.traits.Info": {
                        "customName": "Example Home",
                    },
                },
            }
        )
    )

    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)

    result = await oauth.async_configure(result, {"code": "1234"})
    await oauth.async_pubsub_flow(result)
    entry = await oauth.async_finish_setup(
        result, {"cloud_project_id": CLOUD_PROJECT_ID}
    )

    assert entry.title == "Example Home"
    assert "token" in entry.data
    assert "subscriber_id" in entry.data
    assert entry.data["cloud_project_id"] == CLOUD_PROJECT_ID


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_HYBRID])
async def test_config_entry_title_multiple_homes(
    hass, oauth, setup_platform, subscriber
):
    """Test handling of multiple Google Homes authorized."""

    device_manager = await subscriber.async_get_device_manager()
    device_manager.add_structure(
        Structure.MakeStructure(
            {
                "name": f"enterprise/{PROJECT_ID}/structures/id-1",
                "traits": {
                    "sdm.structures.traits.Info": {
                        "customName": "Example Home #1",
                    },
                },
            }
        )
    )
    device_manager.add_structure(
        Structure.MakeStructure(
            {
                "name": f"enterprise/{PROJECT_ID}/structures/id-2",
                "traits": {
                    "sdm.structures.traits.Info": {
                        "customName": "Example Home #2",
                    },
                },
            }
        )
    )

    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)

    result = await oauth.async_configure(result, {"code": "1234"})
    await oauth.async_pubsub_flow(result)
    entry = await oauth.async_finish_setup(
        result, {"cloud_project_id": CLOUD_PROJECT_ID}
    )
    assert entry.title == "Example Home #1, Example Home #2"


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_HYBRID])
async def test_title_failure_fallback(hass, oauth, setup_platform, mock_subscriber):
    """Test exception handling when determining the structure names."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)

    mock_subscriber.async_get_device_manager.side_effect = AuthException()

    result = await oauth.async_configure(result, {"code": "1234"})
    await oauth.async_pubsub_flow(result)
    entry = await oauth.async_finish_setup(
        result, {"cloud_project_id": CLOUD_PROJECT_ID}
    )

    assert entry.title == "OAuth for Apps"
    assert "token" in entry.data
    assert "subscriber_id" in entry.data
    assert entry.data["cloud_project_id"] == CLOUD_PROJECT_ID


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_HYBRID])
async def test_structure_missing_trait(hass, oauth, setup_platform, subscriber):
    """Test handling the case where a structure has no name set."""

    device_manager = await subscriber.async_get_device_manager()
    device_manager.add_structure(
        Structure.MakeStructure(
            {
                "name": f"enterprise/{PROJECT_ID}/structures/id-1",
                # Missing Info trait
                "traits": {},
            }
        )
    )

    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)

    result = await oauth.async_configure(result, {"code": "1234"})
    await oauth.async_pubsub_flow(result)
    entry = await oauth.async_finish_setup(
        result, {"cloud_project_id": CLOUD_PROJECT_ID}
    )

    # Fallback to default name
    assert entry.title == "OAuth for Apps"


@pytest.mark.parametrize("nest_test_config", [NestTestConfig({})])
async def test_dhcp_discovery(hass, oauth, subscriber):
    """Exercise discovery dhcp starts the config flow and kicks user to frontend creds flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=FAKE_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["step_id"] == "create_cloud_project"

    result = await oauth.async_configure(result, {})
    assert result.get("type") == "abort"
    assert result.get("reason") == "missing_credentials"


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_YAML_ONLY])
async def test_dhcp_discovery_yaml(hass, oauth, setup_platform):
    """Discover via dhcp when config is present."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=FAKE_DHCP_DATA,
    )
    await hass.async_block_till_done()

    # DHCP discovery invokes the config flow
    result = await oauth.async_pick_flow(result, WEB_AUTH_DOMAIN)
    await oauth.async_oauth_web_flow(result)
    entry = await oauth.async_finish_setup(result)
    assert entry.title == "OAuth for Web"

    # Discovery does not run once configured
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=FAKE_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIGFLOW_APP_CREDS])
async def test_dhcp_discovery_with_creds(hass, oauth, subscriber, setup_platform):
    """Exercise discovery dhcp with no config present (can't run)."""
    await setup_platform()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=FAKE_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert result.get("type") == "form"
    assert result.get("step_id") == "cloud_project"

    result = await oauth.async_configure(result, {"cloud_project_id": CLOUD_PROJECT_ID})
    assert result.get("type") == "form"
    assert result.get("step_id") == "device_project"

    result = await oauth.async_configure(result, {"project_id": PROJECT_ID})
    await oauth.async_oauth_web_flow(result)
    entry = await oauth.async_finish_setup(result, {"code": "1234"})
    await hass.async_block_till_done()

    data = dict(entry.data)
    assert "token" in data
    data["token"].pop("expires_in")
    data["token"].pop("expires_at")
    assert "subscriber_id" in data
    assert f"projects/{CLOUD_PROJECT_ID}/subscriptions" in data["subscriber_id"]
    data.pop("subscriber_id")
    assert data == {
        "sdm": {},
        "auth_implementation": "imported-cred",
        "cloud_project_id": CLOUD_PROJECT_ID,
        "project_id": PROJECT_ID,
        "token": {
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
        },
    }
