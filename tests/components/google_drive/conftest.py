"""PyTest fixtures and test helpers."""

from collections.abc import Generator
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.backup import AddonInfo, AgentBackup
from homeassistant.components.google_drive.const import DOMAIN
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_conversion import InformationConverter

from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
HA_UUID = "0a123c"
TEST_AGENT_ID = "google_drive.testuser_domain_com"
TEST_USER_EMAIL = "testuser@domain.com"
CONFIG_ENTRY_TITLE = "Google Drive entry title"


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture
def mock_api() -> Generator[MagicMock]:
    """Return a mocked GoogleDriveApi."""
    with patch(
        "homeassistant.components.google_drive.api.GoogleDriveApi"
    ) as mock_api_cl:
        mock_api = mock_api_cl.return_value

        def mock_get_user(params=None):
            params = params or {}
            fields = params.get("fields")
            result = {}
            if not fields or "storageQuota" in fields:
                result["storageQuota"] = {
                    "limit": InformationConverter.convert(
                        10, UnitOfInformation.GIBIBYTES, UnitOfInformation.BYTES
                    ),
                    "usage": InformationConverter.convert(
                        5, UnitOfInformation.GIBIBYTES, UnitOfInformation.BYTES
                    ),
                    "usageInDrive": InformationConverter.convert(
                        2, UnitOfInformation.GIBIBYTES, UnitOfInformation.BYTES
                    ),
                    "usageInTrash": InformationConverter.convert(
                        1, UnitOfInformation.GIBIBYTES, UnitOfInformation.BYTES
                    ),
                }
            if not fields or "user(emailAddress)" in fields:
                result["user"] = {"emailAddress": TEST_USER_EMAIL}

            return result

        mock_api.get_user = AsyncMock(side_effect=mock_get_user)
        # Setup looks up existing folder to make sure it still exists
        # and list backups during coordinator update
        mock_api.list_files = AsyncMock(
            side_effect=[
                {"files": [{"id": "HA folder ID", "name": "HA folder name"}]},
                {"files": []},
            ]
        )
        yield mock_api


@pytest.fixture(autouse=True)
def mock_instance_id() -> Generator[AsyncMock]:
    """Mock instance_id."""
    with patch(
        "homeassistant.components.google_drive.config_flow.instance_id.async_get",
        return_value=HA_UUID,
    ):
        yield


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture(name="config_entry")
def mock_config_entry(expires_at: int) -> MockConfigEntry:
    """Fixture for MockConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USER_EMAIL,
        title=CONFIG_ENTRY_TITLE,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": "https://www.googleapis.com/auth/drive.file",
            },
        },
    )


@pytest.fixture
def mock_agent_backup() -> AgentBackup:
    """Return a mocked AgentBackup."""
    return AgentBackup(
        addons=[AddonInfo(name="Test", slug="test", version="1.0.0")],
        backup_id="test-backup",
        database_included=True,
        date="2025-01-01T01:23:45.678Z",
        extra_metadata={
            "with_automatic_settings": False,
        },
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2024.12.0",
        name="Test",
        protected=False,
        size=InformationConverter.convert(
            100, UnitOfInformation.MEBIBYTES, UnitOfInformation.BYTES
        ),
    )
