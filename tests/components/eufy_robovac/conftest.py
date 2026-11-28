"""Fixtures for the Eufy RoboVac integration tests."""

from unittest.mock import AsyncMock

from eufy_robovac import RoboVac, RoboVacActivity, RoboVacInfo, RoboVacState
import pytest

from homeassistant.components.eufy_robovac.const import (
    CONF_LOCAL_KEY,
    CONF_PROTOCOL_VERSION,
    DOMAIN,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_MODEL, CONF_NAME

from tests.common import MockConfigEntry

DEVICE_ID = "abc123"
ENTITY_ID = "vacuum.hall_vacuum"
MOCK_INFO = RoboVacInfo(
    device_id=DEVICE_ID,
    model="T2253",
    name="Hall Vacuum",
    local_key="abcdefghijklmnop",
    host="192.168.1.50",
    mac="AA:BB:CC:DD:EE:FF",
    description="RoboVac",
    protocol_version="3.3",
)
MOCK_STATE = RoboVacState(
    activity=RoboVacActivity.IDLE,
    error=None,
    raw_status="standby",
    raw_error="0",
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock Eufy RoboVac config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_INFO.name,
        unique_id=MOCK_INFO.device_id,
        data={
            CONF_NAME: MOCK_INFO.name,
            CONF_MODEL: MOCK_INFO.model,
            CONF_DEVICE_ID: MOCK_INFO.device_id,
            CONF_LOCAL_KEY: MOCK_INFO.local_key,
            CONF_HOST: MOCK_INFO.host,
            CONF_PROTOCOL_VERSION: MOCK_INFO.protocol_version,
        },
    )


@pytest.fixture
def mock_robovac() -> AsyncMock:
    """Return a mocked communication-library client."""
    robovac = AsyncMock(spec=RoboVac)
    robovac.info = MOCK_INFO
    robovac.state = MOCK_STATE
    robovac.update.return_value = MOCK_STATE
    return robovac
