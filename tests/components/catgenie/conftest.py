"""Common fixtures for the CatGenie tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from catgenie import Credentials, Device
import pytest

from homeassistant.components.catgenie.const import DOMAIN
from homeassistant.const import CONF_TOKEN

from tests.common import MockConfigEntry

MOCK_CREDENTIALS = Credentials(
    access_token="test-access-token",
    refresh_token="test-refresh-token",
    token_expiration=9999999999.0,
    account_id="test-account-id",
    user_id="test-user-id",
    tenant_id="test-tenant-id",
)

MOCK_ENTRY_DATA = {
    CONF_TOKEN: "test-refresh-token",
}

MOCK_DEVICE_DATA = {
    "manufacturerId": "DEVICE001",
    "name": "CatGenie Litter Box",
    "macAddress": "AA:BB:CC:DD:EE:FF",
    "hwRevision": "1.0",
    "fwVersion": "2.5.1",
    "type": 0,
    "pumpTypeEnum": "",
    "status": 2,
    "reportedStatus": "connected",
    "connectionMode": "wifi",
    "lastClean": "2024-01-15T10:30:00Z",
    "remainingSaniSolution": 75,
    "serviceLevel": "",
    "countryCode": 61,
    "lowHeater": False,
    "fanShutter": False,
    "dome": False,
    "configuration": {
        "childLock": 0,
        "autoLock": 0,
        "volumeLevel": 7,
        "mode": 0,
        "catSense": 16,
        "timezone": "+10:00",
        "catDelay": 600,
        "pumpPctT": 100,
        "extraDry": False,
        "schedule": [],
        "activation": {
            "date": "2023-06-01T00:00:00Z",
            "state": 1,
            "count": 150,
        },
    },
    "operationStatus": {
        "state": 0,
        "progress": 255,
    },
    "activeErrors": [],
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY_DATA,
        unique_id="test-user-id",
        title="CatGenie (499999999)",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.catgenie.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_catgenie_auth() -> Generator[MagicMock]:
    """Mock CatGenieAuth."""
    with patch(
        "homeassistant.components.catgenie.config_flow.CatGenieAuth",
        autospec=True,
    ) as mock_auth_cls:
        mock_auth = mock_auth_cls.return_value
        mock_auth.__aenter__ = AsyncMock(return_value=mock_auth)
        mock_auth.__aexit__ = AsyncMock(return_value=None)
        mock_auth.request_login_code = AsyncMock(
            return_value={"status": 200, "data": {}}
        )
        mock_auth.login = AsyncMock(return_value=MOCK_CREDENTIALS)
        mock_auth.refresh = AsyncMock(return_value=MOCK_CREDENTIALS)
        mock_auth.credentials = MOCK_CREDENTIALS
        yield mock_auth


@pytest.fixture
def mock_catgenie_client() -> Generator[MagicMock]:
    """Mock CatGenieClient."""
    with patch(
        "homeassistant.components.catgenie.CatGenieClient",
        autospec=True,
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get_devices = AsyncMock(
            return_value=[Device.model_validate(MOCK_DEVICE_DATA)]
        )
        yield mock_client


@pytest.fixture
def mock_catgenie_auth_init() -> Generator[MagicMock]:
    """Mock CatGenieAuth for __init__.py."""
    with patch(
        "homeassistant.components.catgenie.CatGenieAuth",
        autospec=True,
    ) as mock_auth_cls:
        mock_auth = mock_auth_cls.return_value
        mock_auth.__aenter__ = AsyncMock(return_value=mock_auth)
        mock_auth.__aexit__ = AsyncMock(return_value=None)
        mock_auth.refresh = AsyncMock(return_value=MOCK_CREDENTIALS)
        mock_auth.credentials = MOCK_CREDENTIALS
        yield mock_auth
