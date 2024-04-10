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
from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.device_manager import DeviceManager
import pytest

from homeassistant.components.application_credentials import (
    async_import_client_credential,
)
from homeassistant.components.nest import DOMAIN
from homeassistant.components.nest.const import CONF_SUBSCRIBER_ID, SDM_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    DEVICE_ID,
    PROJECT_ID,
    SUBSCRIBER_ID,
    TEST_CONFIG_APP_CREDS,
    CreateDevice,
    FakeSubscriber,
    NestTestConfig,
    PlatformSetup,
    YieldFixture,
)

from tests.common import MockConfigEntry

FAKE_TOKEN = "some-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"


class FakeAuth(AbstractAuth):
    """A fake implementation of the auth class that records requests.

    This class captures the outgoing requests, and can also be used by
    tests to set up fake responses.  This class is registered as a response
    handler for a fake aiohttp_server and can simulate successes or failures
    from the API.
    """

    def __init__(self):
        """Initialize FakeAuth."""
        super().__init__(None, None)
        # Tests can set fake responses here.
        self.responses = []
        # The last request is recorded here.
        self.method = None
        self.url = None
        self.json = None
        self.headers = None
        self.captured_requests = []
        # Set up by fixture
        self.client = None

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return ""

    async def request(self, method, url, **kwargs):
        """Capure the request arguments for tests to assert on."""
        self.method = method
        self.url = url
        self.json = kwargs.get("json")
        self.headers = kwargs.get("headers")
        self.captured_requests.append((method, url, self.json, self.headers))
        return await self.client.get("/")

    async def response_handler(self, request):
        """Handle fake responess for aiohttp_server."""
        if len(self.responses) > 0:
            return self.responses.pop(0)
        return aiohttp.web.json_response()


@pytest.fixture
def aiohttp_client(event_loop, aiohttp_client, socket_enabled):
    """Return aiohttp_client and allow opening sockets."""
    return aiohttp_client


@pytest.fixture
async def auth(aiohttp_client):
    """Fixture for an AbstractAuth."""
    auth = FakeAuth()
    app = aiohttp.web.Application()
    app.router.add_get("/", auth.response_handler)
    app.router.add_post("/", auth.response_handler)
    auth.client = await aiohttp_client(app)
    return auth


@pytest.fixture(autouse=True)
def cleanup_media_storage(hass):
    """Test cleanup, remove any media storage persisted during the test."""
    tmp_path = str(uuid.uuid4())
    with patch("homeassistant.components.nest.media_source.MEDIA_PATH", new=tmp_path):
        yield
        shutil.rmtree(hass.config.path(tmp_path), ignore_errors=True)


@pytest.fixture
def subscriber() -> YieldFixture[FakeSubscriber]:
    """Set up the FakeSusbcriber."""
    subscriber = FakeSubscriber()
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber",
        return_value=subscriber,
    ):
        yield subscriber


@pytest.fixture
def mock_subscriber() -> YieldFixture[AsyncMock]:
    """Fixture for injecting errors into the subscriber."""
    mock_subscriber = AsyncMock(FakeSubscriber)
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber",
        return_value=mock_subscriber,
    ):
        yield mock_subscriber


@pytest.fixture
async def device_manager(subscriber: FakeSubscriber) -> DeviceManager:
    """Set up the DeviceManager."""
    return await subscriber.async_get_device_manager()


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
    device_manager: DeviceManager,
    auth: FakeAuth,
    device_id: str,
    device_type: str,
    device_traits: dict[str, Any],
) -> None:
    """Fixture for creating devices."""
    factory = CreateDevice(device_manager, auth)
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
def nest_test_config(request) -> NestTestConfig:
    """Fixture that sets up the configuration used for the test."""
    return TEST_CONFIG_APP_CREDS


@pytest.fixture
def config(
    subscriber_id: str | None, nest_test_config: NestTestConfig
) -> dict[str, Any]:
    """Fixture that sets up the configuration.yaml for the test."""
    config = copy.deepcopy(nest_test_config.config)
    if CONF_SUBSCRIBER_ID in config.get(DOMAIN, {}):
        if subscriber_id:
            config[DOMAIN][CONF_SUBSCRIBER_ID] = subscriber_id
        else:
            del config[DOMAIN][CONF_SUBSCRIBER_ID]
    return config


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
    config: dict[str, Any],
    config_entry: MockConfigEntry | None,
) -> YieldFixture[PlatformSetup]:
    """Fixture to setup the integration platform."""
    if config_entry:
        config_entry.add_to_hass(hass)
    with patch("homeassistant.components.nest.PLATFORMS", platforms):

        async def _setup_func() -> bool:
            assert await async_setup_component(hass, DOMAIN, config)
            await hass.async_block_till_done()

        yield _setup_func


@pytest.fixture
async def setup_platform(
    setup_base_platform: PlatformSetup, subscriber: FakeSubscriber
) -> PlatformSetup:
    """Fixture to setup the integration platform and subscriber."""
    return setup_base_platform


@pytest.fixture(autouse=True)
def reset_diagnostics() -> Generator[None, None, None]:
    """Fixture to reset client library diagnostic counters."""
    yield
    diagnostics.reset()
