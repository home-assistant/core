"""Provide common fixtures for the YoLink integration tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from yolink.home_manager import YoLinkHome
from yolink.model import BRDP

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.yolink.api import ConfigEntryAuth
from homeassistant.components.yolink.const import (
    AUTH_TYPE_UAC,
    CONF_AUTH_TYPE,
    CONF_HOME_ID,
    CONF_SECRET_KEY,
    CONF_UAID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_object_fixture

CLIENT_ID = "12345"
CLIENT_SECRET = "6789"

TEST_UAID = "test-uaid-12345"
TEST_SECRET_KEY = "test-secret-key-6789"
TEST_HOME_ID = "home_12345"
TEST_HOME_NAME = "My Test Home"


def home_info_response(
    home_id: str = TEST_HOME_ID, name: str | None = TEST_HOME_NAME
) -> BRDP:
    """Return a Home.getGeneralInfo response for a home."""
    data: dict[str, Any] = {"id": home_id}
    if name is not None:
        data["name"] = name
    return BRDP(code="000000", data=data)


def build_yolink_home() -> AsyncMock:
    """Return a mocked YoLink home instance."""
    home_instance = AsyncMock(spec=YoLinkHome)
    home_instance.async_get_home_info.return_value = home_info_response()
    return home_instance


@pytest.fixture
def water_meter_report() -> dict[str, Any]:
    """Return a redacted YS5018 water meter report."""
    return load_json_object_fixture("ys5018_report.json", DOMAIN)


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.yolink.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(name="mock_auth_manager")
def mock_auth_manager() -> Generator[MagicMock]:
    """Mock the authentication manager."""
    with patch(
        "homeassistant.components.yolink.api.ConfigEntryAuth", autospec=True
    ) as mock_auth:
        mock_auth.return_value = MagicMock(spec=ConfigEntryAuth)
        yield mock_auth


@pytest.fixture(name="mock_yolink_home")
def mock_yolink_home() -> Generator[AsyncMock]:
    """Mock YoLink home instance."""
    with patch(
        "homeassistant.components.yolink.YoLinkHome", autospec=True
    ) as mock_home:
        mock_home.return_value = build_yolink_home()
        yield mock_home


@pytest.fixture(name="mock_yolink_client")
def mock_yolink_client() -> Generator[AsyncMock]:
    """Mock the YoLink API client used by the config flow."""
    with patch(
        "homeassistant.components.yolink.config_flow.YoLinkClient", autospec=True
    ) as mock_client:
        mock_client.return_value.execute.return_value = home_info_response()
        yield mock_client


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock an OAuth2 config entry for YoLink.

    Predates UAC support, so it carries no auth type.
    """
    config_entry = MockConfigEntry(
        unique_id=DOMAIN,
        domain=DOMAIN,
        title="yolink",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "scope": "create",
            },
        },
        options={},
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def mock_uac_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a UAC config entry for YoLink."""
    config_entry = MockConfigEntry(
        unique_id=TEST_HOME_ID,
        domain=DOMAIN,
        title=TEST_HOME_NAME,
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_UAC,
            CONF_UAID: TEST_UAID,
            CONF_SECRET_KEY: TEST_SECRET_KEY,
            CONF_HOME_ID: TEST_HOME_ID,
        },
        options={},
    )
    config_entry.add_to_hass(hass)
    return config_entry
