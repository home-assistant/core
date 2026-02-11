"""Test the Google Nest Device Access config flow."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

from google_nest_sdm.exceptions import AuthException
import pytest

from homeassistant import config_entries
from homeassistant.components.nest.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .common import (
    CLIENT_ID,
    CLOUD_PROJECT_ID,
    PROJECT_ID,
    SUBSCRIBER_ID,
    TEST_CONFIG_APP_CREDS,
    TEST_CONFIGFLOW_APP_CREDS,
    NestTestConfig,
)
from .conftest import FakeAuth, PlatformSetup

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

WEB_REDIRECT_URL = "https://example.com/auth/external/callback"
APP_REDIRECT_URL = "urn:ietf:wg:oauth:2.0:oob"
RAND_SUFFIX = "ABCDEF"

FAKE_DHCP_DATA = DhcpServiceInfo(
    ip="127.0.0.2", macaddress="001122334455", hostname="fake_hostname"
)


@pytest.fixture
def nest_test_config() -> NestTestConfig:
    """Fixture with empty configuration and no existing config entry."""
    return TEST_CONFIGFLOW_APP_CREDS


@pytest.fixture(autouse=True)
def mock_rand_topic_name_fixture() -> None:
    """Set the topic name random string to a constant."""
    with patch(
        "homeassistant.components.nest.config_flow.get_random_string",
        return_value=RAND_SUFFIX,
    ):
        yield


@pytest.fixture(autouse=True)
def mock_request_setup(auth: FakeAuth) -> None:
    """Fixture to ensure fake requests are setup."""


class OAuthFixture:
    """Simulate the oauth flow used by the config flow."""

    def __init__(
        self,
        hass: HomeAssistant,
        hass_client_no_auth: ClientSessionGenerator,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """Initialize OAuthFixture."""
        self.hass = hass
        self.hass_client = hass_client_no_auth
        self.aioclient_mock = aioclient_mock

    async def async_app_creds_flow(
        self,
        result: dict,
        cloud_project_id: str = CLOUD_PROJECT_ID,
        project_id: str = PROJECT_ID,
    ) -> None:
        """Invoke multiple steps in the app credentials based flow."""
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "cloud_project"

        result = await self.async_configure(
            result, {"cloud_project_id": CLOUD_PROJECT_ID}
        )
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "device_project"

        result = await self.async_configure(result, {"project_id": project_id})
        await self.async_oauth_web_flow(result, project_id=project_id)

    async def async_oauth_web_flow(self, result: dict, project_id=PROJECT_ID) -> None:
        """Invoke the oauth flow for Web Auth with fake responses."""
        state = self.create_state(result, WEB_REDIRECT_URL)
        assert result["type"] is FlowResultType.EXTERNAL_STEP
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

    async def async_reauth(self, config_entry: ConfigEntry) -> dict:
        """Initiate a reuath flow."""
        config_entry.async_start_reauth(self.hass)
        await self.hass.async_block_till_done()

        # Advance through the reauth flow
        result = self.async_progress()
        assert result["step_id"] == "reauth_confirm"

        # Advance to the oauth flow
        return await self.hass.config_entries.flow.async_configure(
            result["flow_id"], {}
        )

    def async_progress(self) -> FlowResult:
        """Return the current step of the config flow."""
        flows = self.hass.config_entries.flow.async_progress()
        assert len(flows) == 1
        return flows[0]

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

    def async_mock_refresh(self) -> None:
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

    async def async_complete_pubsub_flow(
        self,
        result: dict,
        selected_topic: str,
        selected_subscription: str = "create_new_subscription",
        user_input: dict | None = None,
        existing_errors: dict | None = None,
    ) -> FlowResult:
        """Fixture to walk through the Pub/Sub topic and subscription steps.

        This picks a simple set of steps that are reusable for most flows without
        exercising the corner cases.
        """

        # Validate Pub/Sub topics are shown
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "pubsub_topic"
        assert not result.get("errors")

        # Select Pub/Sub topic the show available subscriptions (none)
        result = await self.async_configure(
            result,
            {
                "topic_name": selected_topic,
            },
        )
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "pubsub_topic_confirm"
        assert not result.get("errors")

        # ACK the topic selection. User is instructed to do some manual
        result = await self.async_configure(result, {})
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == "pubsub_subscription"
        assert not result.get("errors")

        # Create the subscription and end the flow
        return await self.async_finish_setup(
            result,
            {
                "subscription_name": selected_subscription,
            },
        )

    async def async_finish_setup(
        self, result: dict, user_input: dict | None = None
    ) -> FlowResult:
        """Finish the OAuth flow exchanging auth token for refresh token."""
        with patch(
            "homeassistant.components.nest.async_setup_entry", return_value=True
        ) as mock_setup:
            new_result = await self.async_configure(result, user_input)
            assert len(mock_setup.mock_calls) == 1
            await self.hass.async_block_till_done()
        return new_result

    async def async_configure(
        self, result: dict[str, Any], user_input: dict[str, Any]
    ) -> FlowResult:
        """Advance to the next step in the config flow."""
        return await self.hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input,
        )

    def get_config_entry(self) -> ConfigEntry:
        """Get the config entry."""
        entries = self.hass.config_entries.async_entries(DOMAIN)
        assert len(entries) >= 1
        return entries[0]


@pytest.fixture
async def oauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
) -> OAuthFixture:
    """Create the simulated oauth flow."""
    return OAuthFixture(hass, hass_client_no_auth, aioclient_mock)


@pytest.fixture(name="sdm_managed_topic")
def mock_sdm_managed_topic() -> bool:
    """Fixture to configure fake server responses for SDM owned Pub/Sub topics."""
    return False


@pytest.fixture(name="user_managed_topics")
def mock_user_managed_topics() -> list[str]:
    """Fixture to configure fake server response for user owned Pub/Sub topics."""
    return []


@pytest.fixture(name="subscriptions")
def mock_subscriptions() -> list[tuple[str, str]]:
    """Fixture to configure fake server response for user subscriptions that exist."""
    return []


@pytest.fixture(name="cloud_project_id")
def mock_cloud_project_id() -> str:
    """Fixture to configure the cloud console project id used in tests."""
    return CLOUD_PROJECT_ID


def setup_mock_list_subscriptions_responses(
    aioclient_mock: AiohttpClientMocker,
    cloud_project_id: str,
    subscriptions: list[tuple[str, str]],
    list_subscriptions_status: HTTPStatus = HTTPStatus.OK,
) -> None:
    """Configure the mock responses for listing Pub/Sub subscriptions."""
    aioclient_mock.get(
        f"https://pubsub.googleapis.com/v1/projects/{cloud_project_id}/subscriptions",
        json={
            "subscriptions": [
                {
                    "name": subscription_name,
                    "topic": topic,
                    "pushConfig": {},
                    "ackDeadlineSeconds": 10,
                    "messageRetentionDuration": "604800s",
                    "expirationPolicy": {"ttl": "2678400s"},
                    "state": "ACTIVE",
                }
                for (subscription_name, topic) in subscriptions or ()
            ]
        },
        status=list_subscriptions_status,
    )


def setup_mock_create_topic_responses(
    aioclient_mock: AiohttpClientMocker,
    cloud_project_id: str,
    create_topic_status: HTTPStatus = HTTPStatus.OK,
) -> None:
    """Configure the mock responses for creating a Pub/Sub topic."""
    aioclient_mock.put(
        f"https://pubsub.googleapis.com/v1/projects/{cloud_project_id}/topics/home-assistant-{RAND_SUFFIX}",
        json={},
        status=create_topic_status,
    )
    aioclient_mock.post(
        f"https://pubsub.googleapis.com/v1/projects/{cloud_project_id}/topics/home-assistant-{RAND_SUFFIX}:setIamPolicy",
        json={},
        status=create_topic_status,
    )


def setup_mock_create_subscription_responses(
    aioclient_mock: AiohttpClientMocker,
    cloud_project_id: str,
    create_subscription_status: HTTPStatus = HTTPStatus.OK,
) -> None:
    """Configure the mock responses for creating a Pub/Sub subscription."""
    aioclient_mock.put(
        f"https://pubsub.googleapis.com/v1/projects/{cloud_project_id}/subscriptions/home-assistant-{RAND_SUFFIX}",
        json={},
        status=create_subscription_status,
    )


class MockPubSubAPIResponses:
    """Configure mock Pub/Sub API responses for config flow tests."""

    def __init__(self, aioclient_mock: AiohttpClientMocker) -> None:
        """Initialize the mock Pub/Sub API responses."""
        self.aioclient_mock = aioclient_mock
        self.sdm_managed_topic = False
        self.user_managed_topics: list[str] = []
        self.subscriptions: list[tuple[str, str]] = []
        self.device_access_project_id = PROJECT_ID
        self.cloud_project_id = CLOUD_PROJECT_ID
        self.create_topic_status = HTTPStatus.OK
        self.create_subscription_status = HTTPStatus.OK
        self.list_topics_status = HTTPStatus.OK
        self.list_subscriptions_status = HTTPStatus.OK

    def register_mock_requests(self) -> None:
        """Configure a server response for an SDM managed Pub/Sub topic.

        We check for a topic created by the SDM Device Access Console (but note we don't have permission to read it)
        or the user has created one themselves in the Google Cloud Project.
        """
        self.aioclient_mock.get(
            f"https://pubsub.googleapis.com/v1/projects/sdm-prod/topics/enterprise-{self.device_access_project_id}",
            status=HTTPStatus.FORBIDDEN
            if self.sdm_managed_topic
            else HTTPStatus.NOT_FOUND,
        )
        self.aioclient_mock.get(
            f"https://pubsub.googleapis.com/v1/projects/{self.cloud_project_id}/topics",
            json={
                "topics": [
                    {
                        "name": topic_name,
                    }
                    for topic_name in self.user_managed_topics or ()
                ]
            },
            status=self.list_topics_status,
        )
        # We check for a topic created by the SDM Device Access Console (but note we don't have permission to read it)
        # or the user has created one themselves in the Google Cloud Project.
        setup_mock_list_subscriptions_responses(
            self.aioclient_mock,
            self.cloud_project_id,
            self.subscriptions,
            self.list_subscriptions_status,
        )
        setup_mock_create_topic_responses(
            self.aioclient_mock, self.cloud_project_id, self.create_topic_status
        )
        setup_mock_create_subscription_responses(
            self.aioclient_mock, self.cloud_project_id, self.create_subscription_status
        )


@pytest.fixture(autouse=True, name="mock_pubsub_api_responses")
def mock_pubsub_api_responses_fixture(
    aioclient_mock: AiohttpClientMocker,
    sdm_managed_topic: bool,
    user_managed_topics: list[str],
    subscriptions: list[tuple[str, str]],
    device_access_project_id: str,
    cloud_project_id: str,
) -> MockPubSubAPIResponses:
    """Fixture to configure mock Pub/Sub API responses for config flow tests."""
    mock_responses = MockPubSubAPIResponses(aioclient_mock)
    mock_responses.sdm_managed_topic = sdm_managed_topic
    mock_responses.user_managed_topics = user_managed_topics
    mock_responses.subscriptions = subscriptions
    mock_responses.device_access_project_id = device_access_project_id
    mock_responses.cloud_project_id = cloud_project_id
    mock_responses.register_mock_requests()
    return mock_responses


@pytest.mark.parametrize(
    (
        "sdm_managed_topic",
        "user_managed_topics",
        "subscriptions",
        "topic_args",
        "expected_config_entry_data",
    ),
    [
        (
            True,
            [],
            [],
            {"selected_topic": "create_new_topic"},
            {
                "topic_name": f"projects/{CLOUD_PROJECT_ID}/topics/home-assistant-{RAND_SUFFIX}",
                "subscription_name": f"projects/{CLOUD_PROJECT_ID}/subscriptions/home-assistant-{RAND_SUFFIX}",
            },
        ),
        (
            False,
            [
                f"projects/{CLOUD_PROJECT_ID}/topics/my-topic",
            ],
            [
                (
                    f"projects/{CLOUD_PROJECT_ID}/subscriptions/my-subscription",
                    f"projects/{CLOUD_PROJECT_ID}/topics/my-topic",
                ),
            ],
            {
                "selected_topic": "create_new_topic",
                "selected_subscription": "create_new_subscription",
            },
            {
                "topic_name": f"projects/{CLOUD_PROJECT_ID}/topics/home-assistant-{RAND_SUFFIX}",
                "subscription_name": f"projects/{CLOUD_PROJECT_ID}/subscriptions/home-assistant-{RAND_SUFFIX}",
            },
        ),
        (
            False,
            [
                f"projects/{CLOUD_PROJECT_ID}/topics/my-topic",
            ],
            [
                (
                    f"projects/{CLOUD_PROJECT_ID}/subscriptions/my-subscription",
                    f"projects/{CLOUD_PROJECT_ID}/topics/my-topic",
                ),
            ],
            {
                "selected_topic": f"projects/{CLOUD_PROJECT_ID}/topics/my-topic",
                "selected_subscription": "create_new_subscription",
            },
            {
                "topic_name": f"projects/{CLOUD_PROJECT_ID}/topics/my-topic",
                "subscription_name": f"projects/{CLOUD_PROJECT_ID}/subscriptions/home-assistant-{RAND_SUFFIX}",
            },
        ),
        (
            False,
            [
                f"projects/{CLOUD_PROJECT_ID}/topics/my-topic",
            ],
            [
                (
                    f"projects/{CLOUD_PROJECT_ID}/subscriptions/my-subscription",
                    f"projects/{CLOUD_PROJECT_ID}/topics/my-topic",
                ),
            ],
            {
                "selected_topic": f"projects/{CLOUD_PROJECT_ID}/topics/my-topic",
                "selected_subscription": f"projects/{CLOUD_PROJECT_ID}/subscriptions/my-subscription",
            },
            {
                "topic_name": f"projects/{CLOUD_PROJECT_ID}/topics/my-topic",
                "subscription_name": f"projects/{CLOUD_PROJECT_ID}/subscriptions/my-subscription",
                "subscriber_id_imported": True,
            },
        ),
    ],
    ids=[
        "sdm-managed-topic",
        "existing-topics-ignored",
        "user-managed-topic",
        "user-managed-topic-existing-subscription",
    ],
)
async def test_full_flow(
    hass: HomeAssistant,
    oauth: OAuthFixture,
    mock_pubsub_api_responses: MockPubSubAPIResponses,
    topic_args: dict[str, str],
    expected_config_entry_data: dict[str, Any],
) -> None:
    """Check full flow."""
    mock_pubsub_api_responses.sdm_managed_topic = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await oauth.async_app_creds_flow(result)
    oauth.async_mock_refresh()

    result = await oauth.async_configure(result, None)
    result = await oauth.async_complete_pubsub_flow(
        result,
        **topic_args,
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("context", {}).get("unique_id") == PROJECT_ID

    entry = oauth.get_config_entry()
    data = dict(entry.data)
    assert "token" in data
    data["token"].pop("expires_in")
    data["token"].pop("expires_at")
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
        **expected_config_entry_data,
    }


@pytest.mark.parametrize(("device_access_project_id"), [("new-project-id")])
@pytest.mark.parametrize(("cloud_project_id"), [("new-cloud-project-id")])
@pytest.mark.parametrize(
    (
        "sdm_managed_topic",
        "user_managed_topics",
        "subscriptions",
        "topic_args",
        "expected_config_entry_data",
    ),
    [
        (
            True,
            [],
            [],
            {"selected_topic": "projects/sdm-prod/topics/enterprise-new-project-id"},
            {
                "topic_name": "projects/sdm-prod/topics/enterprise-new-project-id",
                "subscription_name": f"projects/new-cloud-project-id/subscriptions/home-assistant-{RAND_SUFFIX}",
            },
        ),
        (
            True,
            [],
            [],
            {"selected_topic": "create_new_topic"},
            {
                "topic_name": f"projects/new-cloud-project-id/topics/home-assistant-{RAND_SUFFIX}",
                "subscription_name": f"projects/new-cloud-project-id/subscriptions/home-assistant-{RAND_SUFFIX}",
            },
        ),
        (
            False,
            [
                "projects/new-project-id/topics/my-topic",
            ],
            [
                (
                    "projects/new-project-id/subscriptions/my-subscription",
                    "projects/new-project-id/topics/my-topic",
                ),
            ],
            {
                "selected_topic": "create_new_topic",
                "selected_subscription": "create_new_subscription",
            },
            {
                "topic_name": f"projects/new-cloud-project-id/topics/home-assistant-{RAND_SUFFIX}",
                "subscription_name": f"projects/new-cloud-project-id/subscriptions/home-assistant-{RAND_SUFFIX}",
            },
        ),
        (
            False,
            [
                "projects/new-cloud-project-id/topics/my-topic",
            ],
            [
                (
                    "projects/new-cloud-project-id/subscriptions/my-subscription",
                    "projects/new-cloud-project-id/topics/my-topic",
                ),
            ],
            {
                "selected_topic": "projects/new-cloud-project-id/topics/my-topic",
                "selected_subscription": "create_new_subscription",
            },
            {
                "topic_name": "projects/new-cloud-project-id/topics/my-topic",
                "subscription_name": f"projects/new-cloud-project-id/subscriptions/home-assistant-{RAND_SUFFIX}",
            },
        ),
        (
            False,
            [
                "projects/new-cloud-project-id/topics/my-topic",
            ],
            [
                (
                    "projects/new-cloud-project-id/subscriptions/my-subscription",
                    "projects/new-cloud-project-id/topics/my-topic",
                ),
            ],
            {
                "selected_topic": "projects/new-cloud-project-id/topics/my-topic",
                "selected_subscription": "projects/new-cloud-project-id/subscriptions/my-subscription",
            },
            {
                "topic_name": "projects/new-cloud-project-id/topics/my-topic",
                "subscription_name": "projects/new-cloud-project-id/subscriptions/my-subscription",
                "subscriber_id_imported": True,
            },
        ),
    ],
    ids=[
        "sdm-managed-topic-only",
        "sdm-managed-topic",
        "existing-topics-ignored",
        "user-managed-topic",
        "user-managed-topic-existing-subscription",
    ],
)
async def test_config_flow_restart(
    hass: HomeAssistant,
    oauth: OAuthFixture,
    topic_args: dict[str, str],
    expected_config_entry_data: dict[str, Any],
) -> None:
    """Check with auth implementation is re-initialized when aborting the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await oauth.async_app_creds_flow(result)
    oauth.async_mock_refresh()

    # At this point, we should have a valid auth implementation configured.
    # Simulate aborting the flow and starting over to ensure we get prompted
    # again to configure everything.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "cloud_project"

    # Change the values to show they are reflected below
    result = await oauth.async_configure(
        result, {"cloud_project_id": "new-cloud-project-id"}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "device_project"

    result = await oauth.async_configure(result, {"project_id": "new-project-id"})
    await oauth.async_oauth_web_flow(result, "new-project-id")
    oauth.async_mock_refresh()

    result = await oauth.async_configure(result, {"code": "1234"})
    result = await oauth.async_complete_pubsub_flow(
        result,
        **topic_args,
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("context", {}).get("unique_id") == "new-project-id"

    entry = oauth.get_config_entry()
    data = dict(entry.data)
    assert "token" in data
    data["token"].pop("expires_in")
    data["token"].pop("expires_at")
    assert data == {
        "sdm": {},
        "auth_implementation": "imported-cred",
        "cloud_project_id": "new-cloud-project-id",
        "project_id": "new-project-id",
        **expected_config_entry_data,
        "token": {
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
        },
    }


@pytest.mark.parametrize(("sdm_managed_topic"), [True])
async def test_config_flow_wrong_project_id(
    hass: HomeAssistant,
    oauth: OAuthFixture,
) -> None:
    """Check the case where the wrong project ids are entered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "cloud_project"

    result = await oauth.async_configure(result, {"cloud_project_id": CLOUD_PROJECT_ID})
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "device_project"

    # Enter the cloud project id instead of device access project id (really we just check
    # they are the same value which is never correct)
    result = await oauth.async_configure(result, {"project_id": CLOUD_PROJECT_ID})
    assert result["type"] is FlowResultType.FORM
    assert "errors" in result
    assert "project_id" in result["errors"]
    assert result["errors"]["project_id"] == "wrong_project_id"

    # Fix with a correct value and complete the rest of the flow
    result = await oauth.async_configure(result, {"project_id": PROJECT_ID})
    await oauth.async_oauth_web_flow(result)
    await hass.async_block_till_done()
    oauth.async_mock_refresh()

    result = await oauth.async_configure(result, {"code": "1234"})
    result = await oauth.async_complete_pubsub_flow(
        result, selected_topic="projects/sdm-prod/topics/enterprise-some-project-id"
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("context", {}).get("unique_id") == PROJECT_ID

    entry = oauth.get_config_entry()
    data = dict(entry.data)
    assert "token" in data
    data["token"].pop("expires_in")
    data["token"].pop("expires_at")
    assert data == {
        "sdm": {},
        "auth_implementation": "imported-cred",
        "cloud_project_id": CLOUD_PROJECT_ID,
        "project_id": PROJECT_ID,
        "subscription_name": "projects/cloud-id-9876/subscriptions/home-assistant-ABCDEF",
        "topic_name": "projects/sdm-prod/topics/enterprise-some-project-id",
        "token": {
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
        },
    }


@pytest.mark.parametrize(("sdm_managed_topic"), [True])
@pytest.mark.parametrize(
    ("create_subscription_status"),
    [HTTPStatus.NOT_FOUND, HTTPStatus.INTERNAL_SERVER_ERROR, HTTPStatus.UNAUTHORIZED],
)
async def test_config_flow_pubsub_create_subscription_failure(
    hass: HomeAssistant,
    oauth: OAuthFixture,
    aioclient_mock: AiohttpClientMocker,
    auth: FakeAuth,
    mock_pubsub_api_responses: MockPubSubAPIResponses,
    create_subscription_status: HTTPStatus,
) -> None:
    """Check full flow fails with configuration error."""
    aioclient_mock.clear_requests()
    auth.register_mock_requests()
    mock_pubsub_api_responses.create_subscription_status = create_subscription_status
    mock_pubsub_api_responses.register_mock_requests()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await oauth.async_app_creds_flow(result)
    oauth.async_mock_refresh()

    result = await oauth.async_configure(result, {"code": "1234"})
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "pubsub_topic"
    assert result.get("data_schema")({}) == {
        "topic_name": f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}",
    }

    # Select Pub/Sub topic the show available subscriptions (none)
    result = await oauth.async_configure(
        result,
        {
            "topic_name": f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}",
        },
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "pubsub_topic_confirm"
    assert not result.get("errors")

    result = await oauth.async_configure(result, {})
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "pubsub_subscription"
    assert result.get("data_schema")({}) == {
        "subscription_name": "create_new_subscription",
    }

    # Failure when creating the subscription
    result = await oauth.async_configure(
        result,
        {
            "subscription_name": "create_new_subscription",
        },
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "pubsub_api_error"}

    # Reset the mock to allow success on the next attempt.
    aioclient_mock.clear_requests()
    auth.register_mock_requests()
    mock_pubsub_api_responses.create_subscription_status = HTTPStatus.OK
    mock_pubsub_api_responses.register_mock_requests()

    result = await oauth.async_configure(
        result,
        {
            "subscription_name": "create_new_subscription",
        },
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("context", {}).get("unique_id") == PROJECT_ID

    entry = oauth.get_config_entry()
    data = dict(entry.data)
    assert "token" in data
    data["token"].pop("expires_in")
    data["token"].pop("expires_at")
    assert data == {
        "sdm": {},
        "auth_implementation": "imported-cred",
        "cloud_project_id": CLOUD_PROJECT_ID,
        "project_id": PROJECT_ID,
        "subscription_name": f"projects/{CLOUD_PROJECT_ID}/subscriptions/home-assistant-{RAND_SUFFIX}",
        "topic_name": f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}",
        "token": {
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
        },
    }


@pytest.mark.parametrize(
    ("nest_test_config", "sdm_managed_topic", "device_access_project_id", "topic_args"),
    [
        (
            TEST_CONFIG_APP_CREDS,
            True,
            "project-id-2",
            {"selected_topic": "projects/sdm-prod/topics/enterprise-project-id-2"},
        ),
        (
            TEST_CONFIG_APP_CREDS,
            False,
            "project-id-2",
            {
                "selected_topic": "create_new_topic",
            },
        ),
    ],
)
async def test_multiple_config_entries(
    hass: HomeAssistant,
    oauth: OAuthFixture,
    setup_platform: Callable[[], Awaitable[None]],
    topic_args: dict[str, str],
) -> None:
    """Verify config flow can be started when existing config entry exists."""
    await setup_platform()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await oauth.async_app_creds_flow(result, project_id="project-id-2")
    oauth.async_mock_refresh()
    result = await oauth.async_configure(result, user_input={})
    result = await oauth.async_complete_pubsub_flow(
        result,
        **topic_args,
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("context", {}).get("unique_id") == "project-id-2"

    entry = oauth.get_config_entry()
    assert entry.title == "Mock Title"
    assert "token" in entry.data

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2


@pytest.mark.parametrize(
    ("nest_test_config", "sdm_managed_topic"),
    [(TEST_CONFIG_APP_CREDS, True), (TEST_CONFIG_APP_CREDS, False)],
)
async def test_duplicate_config_entries(
    hass: HomeAssistant, oauth, setup_platform
) -> None:
    """Verify that config entries must be for unique projects."""
    await setup_platform()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "cloud_project"

    result = await oauth.async_configure(result, {"cloud_project_id": CLOUD_PROJECT_ID})
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "device_project"

    result = await oauth.async_configure(result, {"project_id": PROJECT_ID})
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.parametrize(
    ("nest_test_config", "sdm_managed_topic"),
    [(TEST_CONFIG_APP_CREDS, True), (TEST_CONFIG_APP_CREDS, False)],
)
async def test_reauth_multiple_config_entries(
    hass: HomeAssistant, oauth, setup_platform, config_entry
) -> None:
    """Test Nest reauthentication with multiple existing config entries."""
    await setup_platform()

    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **config_entry.data,
            "extra_data": True,
        },
    )
    old_entry.add_to_hass(hass)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2

    orig_subscriber_id = config_entry.data.get("subscriber_id")

    # Invoke the reauth flow
    result = await oauth.async_reauth(config_entry)

    await oauth.async_oauth_web_flow(result)
    oauth.async_mock_refresh()

    result = await oauth.async_finish_setup(result)
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"

    # Only reauth entry was updated, the other entry is preserved
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2
    entry = entries[0]
    assert entry.unique_id == PROJECT_ID
    entry.data["token"].pop("expires_at")
    assert entry.data["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }
    assert entry.data.get("subscriber_id") == orig_subscriber_id  # Not updated
    assert not entry.data.get("extra_data")

    # Other entry was not refreshed
    entry = entries[1]
    entry.data["token"].pop("expires_at")
    assert entry.data.get("token", {}).get("access_token") == "some-token"
    assert entry.data.get("extra_data")


@pytest.mark.parametrize(
    ("nest_test_config", "sdm_managed_topic"),
    [(TEST_CONFIG_APP_CREDS, True), (TEST_CONFIG_APP_CREDS, False)],
)
async def test_pubsub_subscriber_config_entry_reauth(
    hass: HomeAssistant,
    oauth: OAuthFixture,
    setup_platform: PlatformSetup,
    config_entry: MockConfigEntry,
) -> None:
    """Test the pubsub subscriber id is preserved during reauth."""
    await setup_platform()

    result = await oauth.async_reauth(config_entry)
    await oauth.async_oauth_web_flow(result)
    oauth.async_mock_refresh()

    # Entering an updated access token refreshes the config entry.
    result = await oauth.async_finish_setup(result, {"code": "1234"})
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"

    entry = oauth.get_config_entry()
    entry.data["token"].pop("expires_at")
    assert entry.unique_id == PROJECT_ID
    assert entry.data["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }
    assert entry.data["auth_implementation"] == "imported-cred"
    assert entry.data["subscriber_id"] == SUBSCRIBER_ID
    assert entry.data["cloud_project_id"] == CLOUD_PROJECT_ID


@pytest.mark.parametrize(("sdm_managed_topic"), [(True)])
async def test_config_entry_title_from_home(
    hass: HomeAssistant,
    oauth: OAuthFixture,
    auth: FakeAuth,
) -> None:
    """Test that the Google Home name is used for the config entry title."""

    auth.structures.append(
        {
            "name": f"enterprise/{PROJECT_ID}/structures/some-structure-id",
            "traits": {
                "sdm.structures.traits.Info": {
                    "customName": "Example Home",
                },
            },
        }
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await oauth.async_app_creds_flow(result)
    oauth.async_mock_refresh()

    result = await oauth.async_configure(result, {"code": "1234"})
    result = await oauth.async_complete_pubsub_flow(
        result, selected_topic=f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}"
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("context", {}).get("unique_id") == PROJECT_ID

    entry = oauth.get_config_entry()
    assert entry.title == "Example Home"
    assert "token" in entry.data
    assert entry.data.get("cloud_project_id") == CLOUD_PROJECT_ID
    assert (
        entry.data.get("subscription_name")
        == f"projects/{CLOUD_PROJECT_ID}/subscriptions/home-assistant-{RAND_SUFFIX}"
    )
    assert (
        entry.data.get("topic_name")
        == f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}"
    )


@pytest.mark.parametrize(
    ("sdm_managed_topic", "topic_args"),
    [
        (True, {"selected_topic": f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}"}),
        (False, {"selected_topic": "create_new_topic"}),
    ],
)
async def test_config_entry_title_multiple_homes(
    hass: HomeAssistant,
    oauth: OAuthFixture,
    auth: FakeAuth,
    topic_args: dict[str, str],
) -> None:
    """Test handling of multiple Google Homes authorized."""
    auth.structures.extend(
        [
            {
                "name": f"enterprise/{PROJECT_ID}/structures/id-1",
                "traits": {
                    "sdm.structures.traits.Info": {
                        "customName": "Example Home #1",
                    },
                },
            },
            {
                "name": f"enterprise/{PROJECT_ID}/structures/id-2",
                "traits": {
                    "sdm.structures.traits.Info": {
                        "customName": "Example Home #2",
                    },
                },
            },
        ]
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await oauth.async_app_creds_flow(result)
    oauth.async_mock_refresh()

    result = await oauth.async_configure(result, {"code": "1234"})
    result = await oauth.async_complete_pubsub_flow(
        result,
        **topic_args,
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("context", {}).get("unique_id") == PROJECT_ID

    entry = oauth.get_config_entry()
    assert entry.title == "Example Home #1, Example Home #2"


@pytest.mark.parametrize(("sdm_managed_topic"), [(True)])
async def test_title_failure_fallback(
    hass: HomeAssistant, oauth, mock_subscriber
) -> None:
    """Test exception handling when determining the structure names."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await oauth.async_app_creds_flow(result)
    oauth.async_mock_refresh()

    mock_subscriber.async_get_device_manager.side_effect = AuthException()

    result = await oauth.async_configure(result, {"code": "1234"})
    result = await oauth.async_complete_pubsub_flow(
        result, selected_topic=f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}"
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("context", {}).get("unique_id") == PROJECT_ID

    entry = oauth.get_config_entry()
    assert entry.title == "Import from configuration.yaml"
    assert "token" in entry.data
    assert entry.data.get("cloud_project_id") == CLOUD_PROJECT_ID
    assert (
        entry.data.get("subscription_name")
        == f"projects/{CLOUD_PROJECT_ID}/subscriptions/home-assistant-{RAND_SUFFIX}"
    )
    assert (
        entry.data.get("topic_name")
        == f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}"
    )


@pytest.mark.parametrize(("sdm_managed_topic"), [(True)])
async def test_structure_missing_trait(
    hass: HomeAssistant, oauth: OAuthFixture, auth: FakeAuth
) -> None:
    """Test handling the case where a structure has no name set."""

    auth.structures.append(
        {
            "name": f"enterprise/{PROJECT_ID}/structures/id-1",
            # Missing Info trait
            "traits": {},
        }
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await oauth.async_app_creds_flow(result)
    oauth.async_mock_refresh()

    result = await oauth.async_configure(result, {"code": "1234"})
    result = await oauth.async_complete_pubsub_flow(
        result, selected_topic=f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}"
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("context", {}).get("unique_id") == PROJECT_ID

    # Fallback to default name
    entry = oauth.get_config_entry()
    assert entry.title == "Import from configuration.yaml"


@pytest.mark.parametrize("nest_test_config", [NestTestConfig()])
async def test_dhcp_discovery(
    hass: HomeAssistant, oauth: OAuthFixture, nest_test_config: NestTestConfig
) -> None:
    """Exercise discovery dhcp starts the config flow and kicks user to frontend creds flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=FAKE_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "oauth_discovery"

    result = await oauth.async_configure(result, {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "create_cloud_project"

    result = await oauth.async_configure(result, {})
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "missing_credentials"


@pytest.mark.parametrize(
    ("nest_test_config", "sdm_managed_topic", "device_access_project_id"),
    [(TEST_CONFIG_APP_CREDS, True, "project-id-2")],
)
async def test_dhcp_discovery_already_setup(
    hass: HomeAssistant, oauth: OAuthFixture, setup_platform
) -> None:
    """Exercise discovery dhcp with existing config entry."""
    await setup_platform()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=FAKE_DHCP_DATA,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    (
        "sdm_managed_topic",
        "user_managed_topics",
        "subscriptions",
        "topic_args",
        "expected_config_entry_data",
    ),
    [
        (
            True,
            [],  # No existing topics
            [],  # No existing subscriptions
            {
                "selected_topic": f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}",
                "selected_subscription": "create_new_subscription",
            },
            {
                "topic_name": f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}",
                "subscription_name": f"projects/{CLOUD_PROJECT_ID}/subscriptions/home-assistant-{RAND_SUFFIX}",
            },
        ),
        (
            True,
            # Existing topics are ignored
            [f"projects/{CLOUD_PROJECT_ID}/topics/some-topic-id"],
            # Existing subscriptions are ignored
            [
                (
                    f"projects/{CLOUD_PROJECT_ID}/subscriptions/some-subscription-id",
                    f"projects/{CLOUD_PROJECT_ID}/topics/some-topic-id",
                )
            ],
            {
                "selected_topic": f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}",
                "selected_subscription": "create_new_subscription",
            },
            {
                "topic_name": f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}",
                "subscription_name": f"projects/{CLOUD_PROJECT_ID}/subscriptions/home-assistant-{RAND_SUFFIX}",
            },
        ),
        (
            False,
            [],  # No existing topics
            [],  # No existing subscriptions
            {
                "selected_topic": "create_new_topic",
            },
            {
                "topic_name": f"projects/{CLOUD_PROJECT_ID}/topics/home-assistant-ABCDEF",
                "subscription_name": f"projects/{CLOUD_PROJECT_ID}/subscriptions/home-assistant-{RAND_SUFFIX}",
            },
        ),
        (
            False,
            [f"projects/{CLOUD_PROJECT_ID}/topics/some-topic-id"],
            [
                (
                    f"projects/{CLOUD_PROJECT_ID}/subscriptions/some-subscription-id",  # Selected subscription
                    f"projects/{CLOUD_PROJECT_ID}/topics/some-topic-id",
                )
            ],
            {
                "selected_topic": f"projects/{CLOUD_PROJECT_ID}/topics/some-topic-id",
                "selected_subscription": f"projects/{CLOUD_PROJECT_ID}/subscriptions/some-subscription-id",
            },
            {
                "topic_name": f"projects/{CLOUD_PROJECT_ID}/topics/some-topic-id",
                "subscription_name": f"projects/{CLOUD_PROJECT_ID}/subscriptions/some-subscription-id",
                "subscriber_id_imported": True,
            },
        ),
    ],
    ids=[
        "sdm-managed-no-existing-subscriptions",
        "sdm-managed-with-existing-subscriptions",
        "user-managed-create-new-topic",
        "user-managed-select-existing-subscription",
    ],
)
async def test_dhcp_discovery_with_creds(
    hass: HomeAssistant,
    oauth: OAuthFixture,
    topic_args: dict[str, str],
    expected_config_entry_data: dict[str, Any],
) -> None:
    """Exercise discovery dhcp with no config present (can't run)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=FAKE_DHCP_DATA,
    )
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "oauth_discovery"

    result = await oauth.async_configure(result, {})
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "cloud_project"

    result = await oauth.async_configure(result, {"cloud_project_id": CLOUD_PROJECT_ID})
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "device_project"

    result = await oauth.async_configure(result, {"project_id": PROJECT_ID})
    await oauth.async_oauth_web_flow(result)
    oauth.async_mock_refresh()

    result = await oauth.async_configure(result, None)
    result = await oauth.async_complete_pubsub_flow(result, **topic_args)
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("context", {}).get("unique_id") == PROJECT_ID

    entry = oauth.get_config_entry()
    data = dict(entry.data)
    assert "token" in data
    data["token"].pop("expires_in")
    data["token"].pop("expires_at")
    assert data == {
        "sdm": {},
        "auth_implementation": "imported-cred",
        "cloud_project_id": CLOUD_PROJECT_ID,
        "project_id": PROJECT_ID,
        **expected_config_entry_data,
        "token": {
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
        },
    }


@pytest.mark.parametrize(
    ("status_code", "error_reason"),
    [
        (HTTPStatus.UNAUTHORIZED, "oauth_unauthorized"),
        (HTTPStatus.NOT_FOUND, "oauth_failed"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, "oauth_failed"),
    ],
)
async def test_token_error(
    hass: HomeAssistant,
    oauth: OAuthFixture,
    status_code: HTTPStatus,
    error_reason: str,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await oauth.async_app_creds_flow(result)
    oauth.aioclient_mock.post(
        OAUTH2_TOKEN,
        status=status_code,
    )

    result = await oauth.async_configure(result, user_input=None)
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == error_reason


@pytest.mark.parametrize(
    ("user_managed_topics", "subscriptions"),
    [
        (
            [f"projects/{CLOUD_PROJECT_ID}/topics/some-topic-id"],
            [
                (
                    f"projects/{CLOUD_PROJECT_ID}/subscriptions/some-subscription-id",
                    f"projects/{CLOUD_PROJECT_ID}/topics/some-topic-id",
                )
            ],
        )
    ],
)
async def test_existing_topic_and_subscription(
    hass: HomeAssistant,
    oauth: OAuthFixture,
) -> None:
    """Test selecting existing user managed topic and subscription."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await oauth.async_app_creds_flow(result)
    oauth.async_mock_refresh()

    result = await oauth.async_configure(result, None)
    result = await oauth.async_complete_pubsub_flow(
        result,
        selected_topic=f"projects/{CLOUD_PROJECT_ID}/topics/some-topic-id",
        selected_subscription=f"projects/{CLOUD_PROJECT_ID}/subscriptions/some-subscription-id",
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("context", {}).get("unique_id") == PROJECT_ID

    entry = oauth.get_config_entry()
    data = dict(entry.data)
    assert "token" in data
    data["token"].pop("expires_in")
    data["token"].pop("expires_at")
    assert data == {
        "sdm": {},
        "auth_implementation": "imported-cred",
        "cloud_project_id": CLOUD_PROJECT_ID,
        "project_id": PROJECT_ID,
        "subscription_name": f"projects/{CLOUD_PROJECT_ID}/subscriptions/some-subscription-id",
        "subscriber_id_imported": True,
        "topic_name": f"projects/{CLOUD_PROJECT_ID}/topics/some-topic-id",
        "token": {
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
        },
    }


async def test_no_eligible_topics(
    hass: HomeAssistant,
    oauth: OAuthFixture,
) -> None:
    """Test the case where there are no eligible pub/sub topics and the topic is created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await oauth.async_app_creds_flow(result)
    oauth.async_mock_refresh()

    result = await oauth.async_configure(result, None)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "pubsub_topic"
    assert not result.get("errors")
    # Option shown to create a new topic
    assert result.get("data_schema")({}) == {
        "topic_name": "create_new_topic",
    }

    result = await oauth.async_complete_pubsub_flow(
        result,
        selected_topic="create_new_topic",
        selected_subscription="create_new_subscription",
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("context", {}).get("unique_id") == PROJECT_ID

    entry = oauth.get_config_entry()
    data = dict(entry.data)
    assert "token" in data
    data["token"].pop("expires_in")
    data["token"].pop("expires_at")
    assert data == {
        "sdm": {},
        "auth_implementation": "imported-cred",
        "cloud_project_id": CLOUD_PROJECT_ID,
        "project_id": PROJECT_ID,
        "subscription_name": f"projects/{CLOUD_PROJECT_ID}/subscriptions/home-assistant-{RAND_SUFFIX}",
        "topic_name": f"projects/{CLOUD_PROJECT_ID}/topics/home-assistant-{RAND_SUFFIX}",
        "token": {
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
        },
    }


async def test_list_topics_failure(
    hass: HomeAssistant,
    oauth: OAuthFixture,
    aioclient_mock: AiohttpClientMocker,
    auth: FakeAuth,
    mock_pubsub_api_responses: MockPubSubAPIResponses,
) -> None:
    """Test selecting existing user managed topic and subscription."""
    aioclient_mock.clear_requests()
    auth.register_mock_requests()
    mock_pubsub_api_responses.list_topics_status = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_pubsub_api_responses.register_mock_requests()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await oauth.async_app_creds_flow(result)
    oauth.async_mock_refresh()

    result = await oauth.async_configure(result, None)
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "pubsub_api_error"


async def test_create_topic_failed(
    hass: HomeAssistant,
    oauth: OAuthFixture,
    aioclient_mock: AiohttpClientMocker,
    cloud_project_id: str,
    subscriptions: list[tuple[str, str]],
    auth: FakeAuth,
    mock_pubsub_api_responses: MockPubSubAPIResponses,
) -> None:
    """Test the case where there are no eligible pub/sub topics and the topic is created."""
    aioclient_mock.clear_requests()
    auth.register_mock_requests()
    mock_pubsub_api_responses.create_topic_status = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_pubsub_api_responses.register_mock_requests()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await oauth.async_app_creds_flow(result)
    oauth.async_mock_refresh()

    result = await oauth.async_configure(result, None)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "pubsub_topic"
    assert not result.get("errors")
    # Option shown to create a new topic
    assert result.get("data_schema")({}) == {
        "topic_name": "create_new_topic",
    }

    result = await oauth.async_configure(result, {"topic_name": "create_new_topic"})
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "pubsub_topic"
    assert result.get("errors") == {"base": "pubsub_api_error"}

    # Re-register mock requests needed for the rest of the test. The topic
    # request will now succeed.
    aioclient_mock.clear_requests()
    setup_mock_create_topic_responses(aioclient_mock, cloud_project_id)
    # Fix up other mock responses cleared above
    auth.register_mock_requests()
    setup_mock_list_subscriptions_responses(
        aioclient_mock,
        cloud_project_id,
        subscriptions,
    )
    setup_mock_create_subscription_responses(aioclient_mock, cloud_project_id)

    result = await oauth.async_configure(result, {"topic_name": "create_new_topic"})
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "pubsub_topic_confirm"
    assert not result.get("errors")

    result = await oauth.async_configure(result, {})
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "pubsub_subscription"
    assert not result.get("errors")

    # Create a subscription for the topic and end the flow
    result = await oauth.async_finish_setup(
        result,
        {"subscription_name": "create_new_subscription"},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("context", {}).get("unique_id") == PROJECT_ID

    entry = oauth.get_config_entry()
    data = dict(entry.data)
    assert "token" in data
    data["token"].pop("expires_in")
    data["token"].pop("expires_at")
    assert data == {
        "sdm": {},
        "auth_implementation": "imported-cred",
        "cloud_project_id": CLOUD_PROJECT_ID,
        "project_id": PROJECT_ID,
        "subscription_name": f"projects/{CLOUD_PROJECT_ID}/subscriptions/home-assistant-{RAND_SUFFIX}",
        "topic_name": f"projects/{CLOUD_PROJECT_ID}/topics/home-assistant-{RAND_SUFFIX}",
        "token": {
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
        },
    }


@pytest.mark.parametrize(("sdm_managed_topic"), [(True)])
async def test_list_subscriptions_failure(
    hass: HomeAssistant,
    oauth: OAuthFixture,
    aioclient_mock: AiohttpClientMocker,
    auth: FakeAuth,
    mock_pubsub_api_responses: MockPubSubAPIResponses,
) -> None:
    """Test selecting existing user managed topic and subscription."""
    aioclient_mock.clear_requests()
    auth.register_mock_requests()
    mock_pubsub_api_responses.list_subscriptions_status = (
        HTTPStatus.INTERNAL_SERVER_ERROR
    )
    mock_pubsub_api_responses.register_mock_requests()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await oauth.async_app_creds_flow(result)
    oauth.async_mock_refresh()

    result = await oauth.async_configure(result, None)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "pubsub_topic"
    assert not result.get("errors")

    # Select Pub/Sub topic the show available subscriptions (none)
    result = await oauth.async_configure(
        result,
        {
            "topic_name": f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}",
        },
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "pubsub_topic_confirm"
    assert not result.get("errors")

    result = await oauth.async_configure(result, {})
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "pubsub_subscription"
    assert result.get("errors") == {"base": "pubsub_api_error"}

    # Continue with the rest of the flow but clear the mocks so that the
    # flow will now succeed.
    aioclient_mock.clear_requests()
    auth.register_mock_requests()
    mock_pubsub_api_responses.register_mock_requests()

    result = await oauth.async_configure(result, {})
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("context", {}).get("unique_id") == PROJECT_ID

    entry = oauth.get_config_entry()
    data = dict(entry.data)
    assert "token" in data
    data["token"].pop("expires_in")
    data["token"].pop("expires_at")
    assert data == {
        "sdm": {},
        "auth_implementation": "imported-cred",
        "cloud_project_id": CLOUD_PROJECT_ID,
        "project_id": PROJECT_ID,
        "subscription_name": f"projects/{CLOUD_PROJECT_ID}/subscriptions/home-assistant-{RAND_SUFFIX}",
        "topic_name": f"projects/sdm-prod/topics/enterprise-{PROJECT_ID}",
        "token": {
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
        },
    }
