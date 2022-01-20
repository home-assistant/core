"""Test the Google Nest Device Access config flow."""

import copy
from unittest.mock import AsyncMock, patch

from google_nest_sdm.exceptions import (
    AuthException,
    ConfigurationException,
    SubscriberException,
)
from google_nest_sdm.structure import Structure
import pytest

from homeassistant import config_entries, setup
from homeassistant.components import dhcp
from homeassistant.components.nest.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .common import FakeSubscriber, MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
PROJECT_ID = "project-id-4321"
SUBSCRIBER_ID = "projects/cloud-id-9876/subscriptions/subscriber-id-9876"
CLOUD_PROJECT_ID = "cloud-id-9876"

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


FAKE_DHCP_DATA = dhcp.DhcpServiceInfo(
    ip="127.0.0.2", macaddress="00:11:22:33:44:55", hostname="fake_hostname"
)


@pytest.fixture
def subscriber() -> FakeSubscriber:
    """Create FakeSubscriber."""
    return FakeSubscriber()


def get_config_entry(hass):
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

        return await self.async_configure(result, {"implementation": auth_domain})

    async def async_oauth_web_flow(self, result: dict) -> None:
        """Invoke the oauth flow for Web Auth with fake responses."""
        state = self.create_state(result, WEB_REDIRECT_URL)
        assert result["url"] == self.authorize_url(state, WEB_REDIRECT_URL)

        # Simulate user redirect back with auth code
        client = await self.hass_client()
        resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
        assert resp.status == 200
        assert resp.headers["content-type"] == "text/html; charset=utf-8"

        await self.async_mock_refresh(result)

    async def async_oauth_app_flow(self, result: dict) -> None:
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

    async def async_configure(self, result: dict, user_input: dict) -> dict:
        """Advance to the next step in the config flow."""
        return await self.hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

    async def async_pubsub_flow(self, result: dict, cloud_project_id="") -> ConfigEntry:
        """Verify the pubsub creation step."""
        # Render form with a link to get an auth token
        assert result["type"] == "form"
        assert result["step_id"] == "pubsub"
        assert "description_placeholders" in result
        assert "url" in result["description_placeholders"]
        assert result["data_schema"]({}) == {"cloud_project_id": cloud_project_id}

    def get_config_entry(self) -> ConfigEntry:
        """Get the config entry."""
        return get_config_entry(self.hass)


@pytest.fixture
async def oauth(hass, hass_client_no_auth, aioclient_mock, current_request_with_host):
    """Create the simulated oauth flow."""
    return OAuthFixture(hass, hass_client_no_auth, aioclient_mock)


async def async_setup_configflow(hass):
    """Set up component so the pubsub subscriber is managed by config flow."""
    config = copy.deepcopy(CONFIG)
    del config[DOMAIN]["subscriber_id"]  # Create in config flow instead
    return await setup.async_setup_component(hass, DOMAIN, config)


async def test_web_full_flow(hass, oauth):
    """Check full flow."""
    assert await setup.async_setup_component(hass, DOMAIN, CONFIG)

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

    result = await oauth.async_reauth(old_entry.data)

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
    assert "subscriber_id" not in entry.data  # not updated


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
    assert "subscriber_id" not in entry.data  # not updated


async def test_reauth_missing_config_entry(hass):
    """Test the reauth flow invoked missing existing data."""
    assert await setup.async_setup_component(hass, DOMAIN, CONFIG)

    # Invoke the reauth flow with no existing data
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data=None
    )
    assert result["type"] == "abort"
    assert result["reason"] == "missing_configuration"


async def test_app_full_flow(hass, oauth):
    """Check full flow."""
    assert await setup.async_setup_component(hass, DOMAIN, CONFIG)

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

    result = await oauth.async_reauth(old_entry.data)
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
    assert "subscriber_id" not in entry.data  # not updated


async def test_pubsub_subscription(hass, oauth, subscriber):
    """Check flow that creates a pub/sub subscription."""
    assert await async_setup_configflow(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)

    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber",
        return_value=subscriber,
    ):
        result = await oauth.async_configure(result, {"code": "1234"})
        await oauth.async_pubsub_flow(result)
        entry = await oauth.async_finish_setup(
            result, {"cloud_project_id": CLOUD_PROJECT_ID}
        )
        await hass.async_block_till_done()

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


async def test_pubsub_subscription_strip_whitespace(hass, oauth, subscriber):
    """Check that project id has whitespace stripped on entry."""
    assert await async_setup_configflow(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)

    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber",
        return_value=subscriber,
    ):
        result = await oauth.async_configure(result, {"code": "1234"})
        await oauth.async_pubsub_flow(result)
        entry = await oauth.async_finish_setup(
            result, {"cloud_project_id": " " + CLOUD_PROJECT_ID + " "}
        )
        await hass.async_block_till_done()

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


async def test_pubsub_subscription_auth_failure(hass, oauth):
    """Check flow that creates a pub/sub subscription."""
    assert await async_setup_configflow(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)
    result = await oauth.async_configure(result, {"code": "1234"})
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.create_subscription",
        side_effect=AuthException(),
    ):
        await oauth.async_pubsub_flow(result)
        result = await oauth.async_configure(
            result, {"cloud_project_id": CLOUD_PROJECT_ID}
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "invalid_access_token"


async def test_pubsub_subscription_failure(hass, oauth):
    """Check flow that creates a pub/sub subscription."""
    assert await async_setup_configflow(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)
    result = await oauth.async_configure(result, {"code": "1234"})
    await oauth.async_pubsub_flow(result)
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.create_subscription",
        side_effect=SubscriberException(),
    ):
        result = await oauth.async_configure(
            result, {"cloud_project_id": CLOUD_PROJECT_ID}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert "errors" in result
    assert "cloud_project_id" in result["errors"]
    assert result["errors"]["cloud_project_id"] == "subscriber_error"


async def test_pubsub_subscription_configuration_failure(hass, oauth):
    """Check flow that creates a pub/sub subscription."""
    assert await async_setup_configflow(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)
    result = await oauth.async_configure(result, {"code": "1234"})
    await oauth.async_pubsub_flow(result)
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.create_subscription",
        side_effect=ConfigurationException(),
    ):
        result = await oauth.async_configure(
            result, {"cloud_project_id": CLOUD_PROJECT_ID}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert "errors" in result
    assert "cloud_project_id" in result["errors"]
    assert result["errors"]["cloud_project_id"] == "bad_project_id"


async def test_pubsub_with_wrong_project_id(hass, oauth):
    """Test a possible common misconfiguration mixing up project ids."""
    assert await async_setup_configflow(hass)

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


async def test_pubsub_subscriber_config_entry_reauth(hass, oauth, subscriber):
    """Test the pubsub subscriber id is preserved during reauth."""
    assert await async_setup_configflow(hass)

    old_entry = create_config_entry(
        hass,
        {
            "auth_implementation": APP_AUTH_DOMAIN,
            "subscriber_id": SUBSCRIBER_ID,
            "cloud_project_id": CLOUD_PROJECT_ID,
            "token": {
                "access_token": "some-revoked-token",
            },
            "sdm": {},
        },
    )
    result = await oauth.async_reauth(old_entry.data)
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


async def test_config_entry_title_from_home(hass, oauth, subscriber):
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

    assert await async_setup_configflow(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)

    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber",
        return_value=subscriber,
    ):
        result = await oauth.async_configure(result, {"code": "1234"})
        await oauth.async_pubsub_flow(result)
        entry = await oauth.async_finish_setup(
            result, {"cloud_project_id": CLOUD_PROJECT_ID}
        )
        await hass.async_block_till_done()

    assert entry.title == "Example Home"
    assert "token" in entry.data
    assert "subscriber_id" in entry.data
    assert entry.data["cloud_project_id"] == CLOUD_PROJECT_ID


async def test_config_entry_title_multiple_homes(hass, oauth, subscriber):
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

    assert await async_setup_configflow(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)

    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber",
        return_value=subscriber,
    ):
        result = await oauth.async_configure(result, {"code": "1234"})
        await oauth.async_pubsub_flow(result)
        entry = await oauth.async_finish_setup(
            result, {"cloud_project_id": CLOUD_PROJECT_ID}
        )
        await hass.async_block_till_done()

    assert entry.title == "Example Home #1, Example Home #2"


async def test_title_failure_fallback(hass, oauth):
    """Test exception handling when determining the structure names."""
    assert await async_setup_configflow(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)

    mock_subscriber = AsyncMock(FakeSubscriber)
    mock_subscriber.async_get_device_manager.side_effect = AuthException()

    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber",
        return_value=mock_subscriber,
    ):
        result = await oauth.async_configure(result, {"code": "1234"})
        await oauth.async_pubsub_flow(result)
        entry = await oauth.async_finish_setup(
            result, {"cloud_project_id": CLOUD_PROJECT_ID}
        )
        await hass.async_block_till_done()

    assert entry.title == "OAuth for Apps"
    assert "token" in entry.data
    assert "subscriber_id" in entry.data
    assert entry.data["cloud_project_id"] == CLOUD_PROJECT_ID


async def test_structure_missing_trait(hass, oauth, subscriber):
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

    assert await async_setup_configflow(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await oauth.async_pick_flow(result, APP_AUTH_DOMAIN)
    await oauth.async_oauth_app_flow(result)

    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber",
        return_value=subscriber,
    ):
        result = await oauth.async_configure(result, {"code": "1234"})
        await oauth.async_pubsub_flow(result)
        entry = await oauth.async_finish_setup(
            result, {"cloud_project_id": CLOUD_PROJECT_ID}
        )
        await hass.async_block_till_done()

    # Fallback to default name
    assert entry.title == "OAuth for Apps"


async def test_dhcp_discovery_without_config(hass, oauth):
    """Exercise discovery dhcp with no config present (can't run)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=FAKE_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] == "abort"
    assert result["reason"] == "missing_configuration"


async def test_dhcp_discovery(hass, oauth):
    """Discover via dhcp when config is present."""
    assert await setup.async_setup_component(hass, DOMAIN, CONFIG)

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
