"""Common fixtures for the Ecovacs tests."""
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from deebot_client.const import PATH_API_APPSVR_APP
from deebot_client.device import Device
from deebot_client.exceptions import ApiError
from deebot_client.models import Credentials
import pytest

from homeassistant.components.ecovacs import PLATFORMS
from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.const import CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import VALID_ENTRY_DATA_CLOUD

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ecovacs.async_setup_entry", return_value=True
    ) as async_setup_entry:
        yield async_setup_entry


@pytest.fixture
def mock_config_entry_data() -> dict[str, Any]:
    """Return the default mocked config entry data."""
    return VALID_ENTRY_DATA_CLOUD


@pytest.fixture
def mock_config_entry(mock_config_entry_data: dict[str, Any]) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=mock_config_entry_data[CONF_USERNAME],
        domain=DOMAIN,
        data=mock_config_entry_data,
    )


@pytest.fixture
def device_fixture() -> str:
    """Device class, which should be returned by the get_devices api call."""
    return "yna5x1"


@pytest.fixture
def mock_authenticator(device_fixture: str) -> Generator[Mock, None, None]:
    """Mock the authenticator."""
    with patch(
        "homeassistant.components.ecovacs.controller.Authenticator",
        autospec=True,
    ) as mock, patch(
        "homeassistant.components.ecovacs.config_flow.Authenticator",
        new=mock,
    ):
        authenticator = mock.return_value
        authenticator.authenticate.return_value = Credentials("token", "user_id", 0)

        devices = [
            load_json_object_fixture(f"devices/{device_fixture}/device.json", DOMAIN)
        ]

        async def post_authenticated(
            path: str,
            json: dict[str, Any],
            *,
            query_params: dict[str, Any] | None = None,
            headers: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            if path == PATH_API_APPSVR_APP:
                return {"code": 0, "devices": devices, "errno": "0"}
            raise ApiError("Path not mocked: {path}")

        authenticator.post_authenticated.side_effect = post_authenticated
        yield authenticator


@pytest.fixture
def mock_authenticator_authenticate(mock_authenticator: Mock) -> AsyncMock:
    """Mock authenticator.authenticate."""
    return mock_authenticator.authenticate


@pytest.fixture
def mock_mqtt_client(mock_authenticator: Mock) -> Mock:
    """Mock the MQTT client."""
    with patch(
        "homeassistant.components.ecovacs.controller.MqttClient",
        autospec=True,
    ) as mock, patch(
        "homeassistant.components.ecovacs.config_flow.MqttClient",
        new=mock,
    ):
        client = mock.return_value
        client._authenticator = mock_authenticator
        client.subscribe.return_value = lambda: None
        yield client


@pytest.fixture
def mock_device_execute() -> AsyncMock:
    """Mock the device execute function."""
    with patch.object(
        Device, "_execute_command", return_value=True
    ) as mock_device_execute:
        yield mock_device_execute


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return PLATFORMS


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_authenticator: Mock,
    mock_mqtt_client: Mock,
    mock_device_execute: AsyncMock,
    platforms: Platform | list[Platform],
) -> MockConfigEntry:
    """Set up the Ecovacs integration for testing."""
    if not isinstance(platforms, list):
        platforms = [platforms]

    with patch(
        "homeassistant.components.ecovacs.PLATFORMS",
        platforms,
    ):
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield mock_config_entry


@pytest.fixture
def controller(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> EcovacsController:
    """Get the controller for the config entry."""
    return hass.data[DOMAIN][init_integration.entry_id]
