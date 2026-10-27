"""Shared fixtures for the CoolBot Pro test suite."""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pycoolbot import CoolbotDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.coolbot.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.util import dt as dt_util

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
        "hardware_status": "OK",
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
    """Return a CoolbotClient double, patched into both call sites.

    Readings are set through ``async_get_devices.return_value``; the real
    ``get_devices`` is the synchronous accessor the async one delegates to, so
    the double mirrors it rather than holding a second copy that could drift.

    Listeners registered by the coordinator are kept on ``client.listeners``,
    and ``push()`` fires them the way an arriving reading would.
    """
    client = AsyncMock()
    client.connected = True
    client.async_get_devices.return_value = [make_device()]
    client.get_devices = MagicMock(
        side_effect=lambda: client.async_get_devices.return_value
    )

    listeners: list[Callable[[], None]] = []

    def add_listener(listener: Callable[[], None]) -> Callable[[], None]:
        listeners.append(listener)

        def remove() -> None:
            if listener in listeners:
                listeners.remove(listener)

        return remove

    client.add_listener = MagicMock(side_effect=add_listener)
    client.listeners = listeners

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
