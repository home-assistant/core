"""Fixtures for Mitsubishi Comfort Cloud."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from mitsubishi_comfort import DeviceInfo
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.mitsubishi_comfort_cloud.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

MOCK_USERNAME = "test@test.com"
MOCK_PASSWORD = "testpass"
MOCK_SERIAL = "SERIAL001"
MOCK_SITE = "site-1"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return an account with no local device data."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        unique_id="user-12345",
    )


@pytest.fixture(autouse=True)
def mock_cloud_account() -> Generator[AsyncMock]:
    """Mock the cloud API while using real CloudIndoorUnit instances."""
    with (
        patch(
            "homeassistant.components.mitsubishi_comfort_cloud.MitsubishiCloudAccount",
            autospec=True,
        ) as mock_cls,
        patch(
            "homeassistant.components.mitsubishi_comfort_cloud.config_flow.MitsubishiCloudAccount",
            new=mock_cls,
        ),
    ):
        account = mock_cls.return_value
        account.user_id = "user-12345"
        account.discover_cloud_devices.return_value = {
            MOCK_SERIAL: DeviceInfo(
                serial=MOCK_SERIAL,
                label="Living Room",
                site_id=MOCK_SITE,
                unit_type="ductless",
                address="",
                mac="",
                password="",
                crypto_serial="",
            )
        }
        account.get_zone_state.return_value = {}
        account.get_device_details.return_value = {
            "connected": True,
            "operationMode": "cool",
            "roomTemp": 23.5,
            "spCool": 24.0,
            "spHeat": 21.0,
            "fanSpeed": "auto",
            "airDirection": "auto",
        }
        account.get_device_profile.return_value = {
            "hasModeCool": True,
            "hasModeHeat": True,
            "hasModeAuto": True,
            "hasVaneDir": True,
            "hasFanSpeedAuto": True,
            "numberOfFanSpeeds": 5,
            "minimumSetPoints": {"cool": 18, "heat": 16},
            "maximumSetPoints": {"cool": 30, "heat": 28},
        }
        account.get_device_status.return_value = {}
        yield account
        account.discover_devices.assert_not_awaited()
        account.fetch_v2_credentials.assert_not_awaited()
        account.get_passwords_via_websocket.assert_not_awaited()
