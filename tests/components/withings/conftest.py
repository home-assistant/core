"""Fixtures for tests."""
from datetime import timedelta
import time
from unittest.mock import AsyncMock, patch

import pytest
from withings_api import (
    MeasureGetMeasResponse,
    NotifyListResponse,
    SleepGetSummaryResponse,
    UserGetDeviceResponse,
)

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.withings.api import ConfigEntryWithingsApi
from homeassistant.components.withings.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import ComponentFactory

from tests.common import MockConfigEntry, load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
SCOPES = [
    "user.info",
    "user.metrics",
    "user.activity",
    "user.sleepevents",
]
TITLE = "henk"
USER_ID = 12345
WEBHOOK_ID = "55a7335ea8dee830eed4ef8f84cda8f6d80b83af0847dc74032e86120bffed5e"


@pytest.fixture
def component_factory(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
):
    """Return a factory for initializing the withings component."""
    with patch(
        "homeassistant.components.withings.common.ConfigEntryWithingsApi"
    ) as api_class_mock:
        yield ComponentFactory(
            hass, api_class_mock, hass_client_no_auth, aioclient_mock
        )


@pytest.fixture(name="scopes")
def mock_scopes() -> list[str]:
    """Fixture to set the scopes present in the OAuth token."""
    return SCOPES


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        DOMAIN,
    )


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture(name="config_entry")
def mock_config_entry(expires_at: int, scopes: list[str]) -> MockConfigEntry:
    """Create Withings entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=str(USER_ID),
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "status": 0,
                "userid": str(USER_ID),
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": ",".join(scopes),
            },
            "profile": TITLE,
            "webhook_id": WEBHOOK_ID,
        },
        options={
            "use_webhook": True,
        },
    )


@pytest.fixture(name="withings")
def mock_withings():
    """Mock withings."""

    mock = AsyncMock(spec=ConfigEntryWithingsApi)
    mock.user_get_device.return_value = UserGetDeviceResponse(
        **load_json_object_fixture("withings/get_device.json")
    )
    mock.async_measure_get_meas.return_value = MeasureGetMeasResponse(
        **load_json_object_fixture("withings/get_meas.json")
    )
    mock.async_sleep_get_summary.return_value = SleepGetSummaryResponse(
        **load_json_object_fixture("withings/get_sleep.json")
    )
    mock.async_notify_list.return_value = NotifyListResponse(
        **load_json_object_fixture("withings/notify_list.json")
    )

    with patch(
        "homeassistant.components.withings.common.ConfigEntryWithingsApi",
        return_value=mock,
    ):
        yield mock


@pytest.fixture(name="disable_webhook_delay")
def disable_webhook_delay():
    """Disable webhook delay."""

    mock = AsyncMock()
    with patch(
        "homeassistant.components.withings.common.SUBSCRIBE_DELAY", timedelta(seconds=0)
    ), patch(
        "homeassistant.components.withings.common.UNSUBSCRIBE_DELAY",
        timedelta(seconds=0),
    ):
        yield mock
