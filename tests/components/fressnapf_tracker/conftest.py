"""Common fixtures for the Fressnapf Tracker tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from fressnapftracker import (
    Device,
    EnergySaving,
    LedActivatable,
    LedBrightness,
    PhoneVerificationResponse,
    Position,
    SmsCodeResponse,
    Tracker,
    TrackerFeatures,
    TrackerSettings,
    UserToken,
)
import pytest

from homeassistant.components.fressnapf_tracker.const import (
    CONF_PHONE_NUMBER,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_PHONE_NUMBER = "+491234567890"
MOCK_USER_ID = 12345
MOCK_ACCESS_TOKEN = "mock_access_token"
MOCK_SERIAL_NUMBER = "ABC123456"
MOCK_DEVICE_TOKEN = "mock_device_token"


def create_mock_tracker() -> Tracker:
    """Create a fresh mock Tracker instance."""
    return Tracker(
        name="Fluffy",
        battery=85,
        charging=False,
        position=Position(
            lat=52.520008,
            lng=13.404954,
            accuracy=10,
            timestamp="2024-01-15T12:00:00Z",
        ),
        tracker_settings=TrackerSettings(
            generation="GPS Tracker 2.0",
            features=TrackerFeatures(
                flash_light=True, energy_saving_mode=True, live_tracking=True
            ),
        ),
        led_brightness=LedBrightness(status="ok", value=50),
        energy_saving=EnergySaving(status="ok", value=1),
        deep_sleep=None,
        led_activatable=LedActivatable(
            has_led=True,
            seen_recently=True,
            nonempty_battery=True,
            not_charging=True,
            overall=True,
        ),
        icon="http://res.cloudinary.com/iot-venture/image/upload/v1717594357/kyaqq7nfitrdvaoakb8s.jpg",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fressnapf_tracker.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_tracker_no_position() -> Tracker:
    """Create a mock Tracker object without position."""
    return Tracker(
        name="Fluffy",
        battery=85,
        charging=False,
        position=None,
        tracker_settings=TrackerSettings(
            generation="GPS Tracker 2.0",
            features=TrackerFeatures(live_tracking=True),
        ),
        led_brightness=None,
        deep_sleep=None,
        led_activatable=None,
    )


@pytest.fixture
def mock_device() -> Device:
    """Create a mock Device object."""
    return Device(
        serialnumber=MOCK_SERIAL_NUMBER,
        token=MOCK_DEVICE_TOKEN,
    )


@pytest.fixture
def mock_auth_client(mock_device: Device) -> Generator[MagicMock]:
    """Mock the AuthClient."""
    with (
        patch(
            "homeassistant.components.fressnapf_tracker.config_flow.AuthClient",
            autospec=True,
        ) as mock_auth_client,
        patch(
            "homeassistant.components.fressnapf_tracker.AuthClient",
            new=mock_auth_client,
        ),
    ):
        client = mock_auth_client.return_value
        client.request_sms_code = AsyncMock(
            return_value=SmsCodeResponse(id=MOCK_USER_ID)
        )
        client.verify_phone_number = AsyncMock(
            return_value=PhoneVerificationResponse(
                user_token=UserToken(
                    access_token=MOCK_ACCESS_TOKEN,
                    refresh_token=None,
                )
            )
        )
        client.get_devices = AsyncMock(return_value=[mock_device])
        yield client


@pytest.fixture
def mock_api_client_init() -> Generator[MagicMock]:
    """Mock the ApiClient used by _tracker_is_valid in __init__.py."""
    with patch(
        "homeassistant.components.fressnapf_tracker.ApiClient",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.get_tracker = AsyncMock(return_value=create_mock_tracker())
        yield client


@pytest.fixture
def mock_api_client_coordinator() -> Generator[MagicMock]:
    """Mock the ApiClient used by the coordinator."""
    with patch(
        "homeassistant.components.fressnapf_tracker.coordinator.ApiClient",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.get_tracker = AsyncMock(return_value=create_mock_tracker())
        client.set_led_brightness = AsyncMock(return_value=None)
        client.set_energy_saving = AsyncMock(return_value=None)
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_PHONE_NUMBER,
        data={
            CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER,
            CONF_USER_ID: MOCK_USER_ID,
            CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN,
        },
        unique_id=str(MOCK_USER_ID),
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client_init: MagicMock,
    mock_api_client_coordinator: MagicMock,
    mock_auth_client: MagicMock,
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
