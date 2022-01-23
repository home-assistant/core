"""Common libraries for test setup."""
from __future__ import annotations

import copy
import shutil
from typing import Any
from unittest.mock import patch
import uuid

import aiohttp
from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.device_manager import DeviceManager
import pytest

from homeassistant.components.nest import DOMAIN
from homeassistant.components.nest.const import CONF_SUBSCRIBER_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    SUBSCRIBER_ID,
    TEST_CONFIG_HYBRID,
    TEST_CONFIG_YAML_ONLY,
    FakeSubscriber,
    NestTestConfig,
    PlatformSetup,
    YieldFixture,
)

from tests.common import MockConfigEntry


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
def aiohttp_client(loop, aiohttp_client, socket_enabled):
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
async def device_manager(subscriber: FakeSubscriber) -> DeviceManager:
    """Set up the DeviceManager."""
    return await subscriber.async_get_device_manager()


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture
def subscriber_id() -> str:
    """Fixture to let tests override subscriber id regardless of configuration type used."""
    return SUBSCRIBER_ID


@pytest.fixture(
    params=[TEST_CONFIG_YAML_ONLY, TEST_CONFIG_HYBRID],
    ids=["yaml-config-only", "hybrid-config"],
)
def nest_test_config(request) -> NestTestConfig:
    """Fixture that sets up the configuration used for the test."""
    return request.param


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
def config_entry(
    subscriber_id: str | None, nest_test_config: NestTestConfig
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
    return MockConfigEntry(domain=DOMAIN, data=data)


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
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
    ), patch("homeassistant.components.nest.PLATFORMS", platforms):

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
