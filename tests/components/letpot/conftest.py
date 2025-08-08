"""Common fixtures for the LetPot tests."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, patch

from letpot.models import (
    DeviceFeature,
    LetPotDevice,
    LetPotDeviceInfo,
    LetPotDeviceStatus,
)
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


def _mock_device_info(device_type: str) -> LetPotDeviceInfo:
    """Return mock device info for the given type."""
    return LetPotDeviceInfo(
        model=device_type,
        model_name=f"LetPot {device_type}",
        model_code=device_type,
        features=_mock_device_features(device_type),
    )


def _mock_device_features(device_type: str) -> DeviceFeature:
    """Return mock device feature support for the given type."""
    if device_type == "LPH31":
        return (
            DeviceFeature.CATEGORY_HYDROPONIC_GARDEN
            | DeviceFeature.LIGHT_BRIGHTNESS_LOW_HIGH
            | DeviceFeature.PUMP_STATUS
        )
    if device_type == "LPH62":
        return (
            DeviceFeature.CATEGORY_HYDROPONIC_GARDEN
            | DeviceFeature.LIGHT_BRIGHTNESS_LEVELS
            | DeviceFeature.NUTRIENT_BUTTON
            | DeviceFeature.PUMP_AUTO
            | DeviceFeature.TEMPERATURE
            | DeviceFeature.TEMPERATURE_SET_UNIT
            | DeviceFeature.WATER_LEVEL
        )
    if device_type == "LPH63":
        return (
            DeviceFeature.CATEGORY_HYDROPONIC_GARDEN
            | DeviceFeature.LIGHT_BRIGHTNESS_LEVELS
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
    if device_type in {"LPH62", "LPH63"}:
        return MAX_STATUS
    raise ValueError(f"No mock data for device type {device_type}")


def _mock_light_brightness_levels(device_type: str) -> list[int]:
    """Return mock brightness levels for the given type."""
    if device_type == "LPH31":
        return [500, 1000]
    if device_type in {"LPH62", "LPH63"}:
        return [125, 250, 375, 500, 625, 750, 875, 1000]
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
def mock_device_client() -> Generator[AsyncMock]:
    """Mock a LetPotDeviceClient."""
    with patch(
        "homeassistant.components.letpot.LetPotDeviceClient",
        autospec=True,
    ) as mock_device_client:
        device_client = mock_device_client.return_value

        subscribe_callbacks: dict[str, Callable] = {}

        def subscribe_side_effect(serial: str, callback: Callable) -> None:
            subscribe_callbacks[serial] = callback

        def request_status_side_effect(serial: str) -> None:
            # Deliver a status update to the subscriber, like the real client
            if (callback := subscribe_callbacks.get(serial)) is not None:
                callback(_mock_device_status(serial[:5]))

        def get_current_status_side_effect(serial: str) -> LetPotDeviceStatus:
            request_status_side_effect(serial)
            return _mock_device_status(serial[:5])

        device_client.device_info.side_effect = lambda serial: _mock_device_info(
            serial[:5]
        )
        device_client.get_light_brightness_levels.side_effect = (
            lambda serial: _mock_light_brightness_levels(serial[:5])
        )
        device_client.get_current_status.side_effect = get_current_status_side_effect
        device_client.request_status_update.side_effect = request_status_side_effect
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
