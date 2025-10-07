"""Test fixtures for Sensirion BLE."""

import pytest

from homeassistant.components.sensirion_ble.const import DOMAIN

from .fixtures import SENSIRION_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info_bleak


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSIRION_SERVICE_INFO.address,
        title="MyCO2 84E3",
    )


@pytest.fixture
async def mock_sensirion_ble(enable_bluetooth):
    """Fixture to inject BLE service info."""
    inject_bluetooth_service_info_bleak(
        enable_bluetooth,
        SENSIRION_SERVICE_INFO,
    )
