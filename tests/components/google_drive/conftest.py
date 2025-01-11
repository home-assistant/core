"""PyTest fixtures and test helpers."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.google_drive.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
HA_UUID = "0a123c"


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
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
        yield mock_api


@pytest.fixture(autouse=True)
def mock_instance_id() -> Generator[AsyncMock]:
    """Mock instance_id."""
    with patch(
        "homeassistant.components.google_drive.config_flow.instance_id.async_get",
    ) as mock_async_get:
        mock_async_get.return_value = HA_UUID
        yield mock_async_get
