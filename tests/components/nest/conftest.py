"""Common libraries for test setup."""

from __future__ import annotations

from collections.abc import Generator
import copy
import shutil
import time
from typing import Any
from unittest.mock import AsyncMock, patch
import uuid

import aiohttp
from google_nest_sdm import diagnostics
from google_nest_sdm.google_nest_subscriber import GoogleNestSubscriber
from google_nest_sdm.streaming_manager import StreamingManager
import pytest
from yarl import URL

from homeassistant.components.application_credentials import (
    async_import_client_credential,
)
from homeassistant.components.nest import DOMAIN
from homeassistant.components.nest.const import API_URL, CONF_SUBSCRIBER_ID, SDM_SCOPES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    DEVICE_ID,
    DEVICE_URL_MATCH,
    PROJECT_ID,
    SUBSCRIBER_ID,
    TEST_CLIP_URL,
    TEST_CONFIG_APP_CREDS,
    TEST_IMAGE_URL,
    CreateDevice,
    NestTestConfig,
    PlatformSetup,
    YieldFixture,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse

FAKE_TOKEN = "some-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"


class FakeAuth:
    """A fixture for request handling that records requests.

    This class is used with AiohttpClientMocker to capture outgoing requests
    and can also be used by tests to set up fake responses.
    """

    def __init__(
        self,
        aioclient_mock: AiohttpClientMocker,
        device_factory: CreateDevice,
        project_id: str,
    ) -> None:
        """Initialize FakeAuth."""
        # Tests can factory fixture to create fake device responses.
        self.device_factory = device_factory
        # Tests can set fake structure responses here.
        self.structures: list[dict[str, Any]] = []
        # Tests can set fake command responses here.
        self.responses: list[aiohttp.web.Response] = []

        # The last request is recorded here.
        self.method = None
        self.url = None
        self.json = None
        self.headers = None
        self.captured_requests = []

        # API makes a call to request structures to initiate pubsub feed, but the
        # integration does not use this.
        aioclient_mock.get(
            f"{API_URL}/enterprises/{project_id}/structures",
            side_effect=self.request_structures,
        )
        aioclient_mock.get(
            f"{API_URL}/enterprises/{project_id}/devices",
            side_effect=self.request_devices,
        )
        aioclient_mock.post(DEVICE_URL_MATCH, side_effect=self.request)
        aioclient_mock.get(TEST_IMAGE_URL, side_effect=self.request)
        aioclient_mock.get(TEST_CLIP_URL, side_effect=self.request)

    async def request_structures(
        self, method: str, url: str, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        """Handle requests to create devices."""
        return AiohttpClientMockResponse(
            method, url, json={"structures": self.structures}
        )

    async def request_devices(
        self, method: str, url: str, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        """Handle requests to create devices."""
        return AiohttpClientMockResponse(
            method, url, json={"devices": self.device_factory.devices}
        )

    async def request(
        self, method: str, url: URL, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        """Capure the request arguments for tests to assert on."""
        self.method = method
        str_url = str(url)
        self.url = str_url[len(API_URL) + 1 :]
        self.json = data
        self.captured_requests.append((method, url, self.json))

        if len(self.responses) > 0:
            response = self.responses.pop(0)
            return AiohttpClientMockResponse(
                method, url, response=response.body, status=response.status
            )
        return AiohttpClientMockResponse(method, url)


@pytest.fixture(name="device_access_project_id")
def mock_device_access_project_id() -> str:
    """Fixture to configure the device access console project id used in tests."""
    return PROJECT_ID


@pytest.fixture
async def auth(
    aioclient_mock: AiohttpClientMocker,
    create_device: CreateDevice,
    device_access_project_id: str,
) -> FakeAuth:
    """Fixture for an AbstractAuth."""
    return FakeAuth(aioclient_mock, create_device, device_access_project_id)


@pytest.fixture(autouse=True)
def cleanup_media_storage(hass: HomeAssistant) -> Generator[None]:
    """Test cleanup, remove any media storage persisted during the test."""
    tmp_path = str(uuid.uuid4())
    with patch("homeassistant.components.nest.media_source.MEDIA_PATH", new=tmp_path):
        yield
        shutil.rmtree(hass.config.path(tmp_path), ignore_errors=True)


@pytest.fixture
def subscriber_side_effect() -> Any | None:
    """Fixture to inject failures into FakeSubscriber start."""
    return None


@pytest.fixture(autouse=True)
def subscriber(subscriber_side_effect: Any | None) -> Generator[AsyncMock]:
    """Fixture to allow tests to emulate the pub/sub subscriber receiving messages."""
    with patch(
        "google_nest_sdm.google_nest_subscriber.StreamingManager", spec=StreamingManager
    ) as mock_manager:
        # Use side_effect to capture the callback
        def mock_init(**kwargs: Any) -> AsyncMock:
            mock_manager.async_receive_event = kwargs["callback"]
            if subscriber_side_effect is not None:
                mock_manager.start.side_effect = subscriber_side_effect
            return mock_manager

        mock_manager.side_effect = mock_init
        yield mock_manager


@pytest.fixture
def mock_subscriber() -> YieldFixture[AsyncMock]:
    """Fixture for injecting errors into the subscriber."""
    mock_subscriber = AsyncMock(GoogleNestSubscriber)
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber",
        return_value=mock_subscriber,
    ):
        yield mock_subscriber


@pytest.fixture
async def device_id() -> str:
    """Fixture to set default device id used when creating devices."""
    return DEVICE_ID


@pytest.fixture
async def device_type() -> str:
    """Fixture to set default device type used when creating devices."""
    return "sdm.devices.types.THERMOSTAT"


@pytest.fixture
async def device_traits() -> dict[str, Any]:
    """Fixture to set default device traits used when creating devices."""
    return {}


@pytest.fixture
async def create_device(
    device_id: str,
    device_type: str,
    device_traits: dict[str, Any],
) -> CreateDevice:
    """Fixture for creating devices."""
    factory = CreateDevice()
    factory.data.update(
        {
            "name": device_id,
            "type": device_type,
            "traits": device_traits,
        }
    )
    return factory


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture
def subscriber_id() -> str:
    """Fixture to let tests override subscriber id regardless of configuration type used."""
    return SUBSCRIBER_ID


@pytest.fixture
def nest_test_config() -> NestTestConfig:
    """Fixture that sets up the configuration used for the test."""
    return TEST_CONFIG_APP_CREDS


@pytest.fixture
def config_entry_unique_id() -> str:
    """Fixture to set ConfigEntry unique id."""
    return PROJECT_ID


@pytest.fixture
def token_expiration_time() -> float:
    """Fixture for expiration time of the config entry auth token."""
    return time.time() + 86400


@pytest.fixture
def token_entry(token_expiration_time: float) -> dict[str, Any]:
    """Fixture for OAuth 'token' data for a ConfigEntry."""
    return {
        "access_token": FAKE_TOKEN,
        "refresh_token": FAKE_REFRESH_TOKEN,
        "scope": " ".join(SDM_SCOPES),
        "token_type": "Bearer",
        "expires_at": token_expiration_time,
    }


@pytest.fixture
def config_entry(
    subscriber_id: str | None,
    nest_test_config: NestTestConfig,
    config_entry_unique_id: str,
    token_entry: dict[str, Any],
) -> MockConfigEntry | None:
    """Fixture that sets up the ConfigEntry for the test."""
    if nest_test_config.config_entry_data is None:
        return None
    data = copy.deepcopy(nest_test_config.config_entry_data)
    if CONF_SUBSCRIBER_ID in data:
        if subscriber_id:
            data[CONF_SUBSCRIBER_ID] = subscriber_id
        else:
            del data[CONF_SUBSCRIBER_ID]
    data["token"] = token_entry
    return MockConfigEntry(domain=DOMAIN, data=data, unique_id=config_entry_unique_id)


@pytest.fixture(autouse=True)
async def credential(hass: HomeAssistant, nest_test_config: NestTestConfig) -> None:
    """Fixture that provides the ClientCredential for the test if any."""
    if not nest_test_config.credential:
        return
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, nest_test_config.credential, "imported-cred"
    )


@pytest.fixture
async def setup_base_platform(
    hass: HomeAssistant,
    platforms: list[str],
    config_entry: MockConfigEntry | None,
    auth: FakeAuth,
) -> YieldFixture[PlatformSetup]:
    """Fixture to setup the integration platform."""
    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.nest.PLATFORMS", platforms):

        async def _setup_func() -> bool:
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        yield _setup_func
        if config_entry.state == ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.fixture
async def setup_platform(
    setup_base_platform: PlatformSetup,
    subscriber: AsyncMock,
) -> PlatformSetup:
    """Fixture to setup the integration platform and subscriber."""
    return setup_base_platform


@pytest.fixture(autouse=True)
def reset_diagnostics() -> Generator[None]:
    """Fixture to reset client library diagnostic counters."""
    yield
    diagnostics.reset()
