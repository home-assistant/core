"""Shared fixtures for the CoolBot Pro test suite."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from pycoolbot import CoolbotDevice
import pytest

from homeassistant.components.coolbot.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

TEST_EMAIL = "user@example.com"
TEST_PASSWORD = "hunter2"


def make_device(
    unique_id: str = "coolbot_aabbccddeeff", **overrides: Any
) -> CoolbotDevice:
    """Return a realistic provisioned CoolBot, overridable per test."""
    fields: dict[str, Any] = {
        "dash_id": 10,
        "device_id": 0,
        "target": "10",
        "name": "Walk-in cooler",
        "unique_id": unique_id,
        "status": "ONLINE",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "is_provisioned": True,
        "available": True,
        "hardware_status": "Cooling",
        "set_point_f": 40.0,
        "room_temp_f": 38.5,
        "fins_temp_f": 30.2,
        "wifi_dbm": -55.0,
        "coolbot_hardware": "6",
        "jumper_firmware": "1.2.3",
        "last_data_at": dt_util.utcnow(),
    }
    fields.update(overrides)
    return CoolbotDevice(**fields)


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Return a CoolbotClient double, patched into both call sites."""
    client = AsyncMock()
    client.connected = True
    client.async_get_devices.return_value = [make_device()]
    with (
        patch(
            "homeassistant.components.coolbot.config_flow.CoolbotClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.coolbot.coordinator.CoolbotClient",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for the test account."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TEST_EMAIL,
        data={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
        unique_id=TEST_EMAIL,
    )
