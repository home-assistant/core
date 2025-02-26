"""Common fixtures for the LetPot tests."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, patch

from letpot.models import DeviceFeature, LetPotDevice, LetPotDeviceStatus
import pytest

from homeassistant.components.letpot.const import (
    CONF_ACCESS_TOKEN_EXPIRES,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_EXPIRES,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL

from . import AUTHENTICATION, MAX_STATUS, SE_STATUS

from tests.common import MockConfigEntry


@pytest.fixture
def device_type() -> str:
    """Return the device type to use for mock data."""
    return "LPH63"


def _mock_device_features(device_type: str) -> DeviceFeature:
    """Return mock device feature support for the given type."""
    if device_type == "LPH31":
        return DeviceFeature.LIGHT_BRIGHTNESS_LOW_HIGH | DeviceFeature.PUMP_STATUS
    if device_type == "LPH63":
        return (
            DeviceFeature.LIGHT_BRIGHTNESS_LEVELS
            | DeviceFeature.NUTRIENT_BUTTON
            | DeviceFeature.PUMP_AUTO
            | DeviceFeature.PUMP_STATUS
            | DeviceFeature.TEMPERATURE
            | DeviceFeature.WATER_LEVEL
        )
    raise ValueError(f"No mock data for device type {device_type}")


def _mock_device_status(device_type: str) -> LetPotDeviceStatus:
    """Return mock device status for the given type."""
    if device_type == "LPH31":
        return SE_STATUS
    if device_type == "LPH63":
        return MAX_STATUS
    raise ValueError(f"No mock data for device type {device_type}")


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.letpot.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_client(device_type: str) -> Generator[AsyncMock]:
    """Mock a LetPotClient."""
    with (
        patch(
            "homeassistant.components.letpot.LetPotClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.letpot.config_flow.LetPotClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.login.return_value = AUTHENTICATION
        client.refresh_token.return_value = AUTHENTICATION
        client.get_devices.return_value = [
            LetPotDevice(
                serial_number=f"{device_type}ABCD",
                name="Garden",
                device_type=device_type,
                is_online=True,
                is_remote=False,
            )
        ]
        yield client


@pytest.fixture
def mock_device_client(device_type: str) -> Generator[AsyncMock]:
    """Mock a LetPotDeviceClient."""
    with patch(
        "homeassistant.components.letpot.coordinator.LetPotDeviceClient",
        autospec=True,
    ) as mock_device_client:
        device_client = mock_device_client.return_value
        device_client.device_features = _mock_device_features(device_type)
        device_client.device_model_code = device_type
        device_client.device_model_name = f"LetPot {device_type}"
        device_status = _mock_device_status(device_type)

        subscribe_callbacks: list[Callable] = []

        def subscribe_side_effect(callback: Callable) -> None:
            subscribe_callbacks.append(callback)

        def status_side_effect() -> None:
            # Deliver a status update to any subscribers, like the real client
            for callback in subscribe_callbacks:
                callback(device_status)

        device_client.get_current_status.side_effect = status_side_effect
        device_client.get_current_status.return_value = device_status
        device_client.last_status.return_value = device_status
        device_client.request_status_update.side_effect = status_side_effect
        device_client.subscribe.side_effect = subscribe_side_effect

        yield device_client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=AUTHENTICATION.email,
        data={
            CONF_ACCESS_TOKEN: AUTHENTICATION.access_token,
            CONF_ACCESS_TOKEN_EXPIRES: AUTHENTICATION.access_token_expires,
            CONF_REFRESH_TOKEN: AUTHENTICATION.refresh_token,
            CONF_REFRESH_TOKEN_EXPIRES: AUTHENTICATION.refresh_token_expires,
            CONF_USER_ID: AUTHENTICATION.user_id,
            CONF_EMAIL: AUTHENTICATION.email,
        },
        unique_id=AUTHENTICATION.user_id,
    )
