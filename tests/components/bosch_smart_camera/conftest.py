"""Fixtures for the Bosch Smart Camera tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from bosch_shc_camera_client.cameras import Camera, CameraModel
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.bosch_smart_camera.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

CAMERA_ID = "11111111-1111-1111-1111-111111111111"
CAMERAS = [
    Camera(
        CAMERA_ID, "Garden", "HOME_Eyes_Outdoor", CameraModel.EYES_OUTDOOR_II, "9.40.25"
    )
]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry with a valid token."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="fake-account-sub",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "fake-access-token",
                "refresh_token": "fake-refresh-token",
                "expires_at": dt_util.utcnow().timestamp() + 3600,
            },
        },
    )


@pytest.fixture(autouse=True)
def mock_list_cameras() -> Generator[AsyncMock]:
    """Mock the camera list of the library."""
    with (
        patch(
            "homeassistant.components.bosch_smart_camera.coordinator.list_cameras",
            autospec=True,
            return_value=list(CAMERAS),
        ) as mock,
        patch(
            "homeassistant.components.bosch_smart_camera.config_flow.list_cameras",
            new=mock,
        ),
    ):
        yield mock


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Register the OAuth2 application credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential("fake-client-id", "fake-client-secret")
    )
