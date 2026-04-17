"""Shared fixtures for EARN-E P1 Meter tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from earn_e_p1 import EarnEP1Device
import pytest

from homeassistant.components.earn_e_p1.const import CONF_SERIAL, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.100"
MOCK_SERIAL = "E0012345678901234"

MOCK_DEVICE_DATA: dict[str, Any] = {
    "power_delivered": 2.5,
    "power_returned": 0.0,
    "voltage_l1": 230.1,
    "current_l1": 10.87,
    "energy_delivered_tariff1": 12345.678,
    "energy_delivered_tariff2": 6789.012,
    "energy_returned_tariff1": 100.0,
    "energy_returned_tariff2": 50.0,
    "gas_delivered": 1234.567,
    "wifiRSSI": -65,
}


def trigger_callback(
    mock_listener: MagicMock,
    device_data: dict[str, Any] | None = None,
    model: str | None = "P1 Meter",
    sw_version: str | None = "1.0.0",
) -> None:
    """Trigger the registered listener callback with device data."""
    if device_data is None:
        device_data = MOCK_DEVICE_DATA
    callback = mock_listener.register.call_args[0][1]
    device = EarnEP1Device(host=MOCK_HOST, serial=MOCK_SERIAL)
    device.model = model
    device.sw_version = sw_version
    device.data = device_data
    callback(device, device_data)


@pytest.fixture(autouse=True)
def mock_listener() -> Generator[MagicMock]:
    """Mock EarnEP1Listener to avoid real UDP sockets."""
    with patch(
        "homeassistant.components.earn_e_p1.EarnEP1Listener", autospec=True
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.start = AsyncMock()
        instance.stop = AsyncMock()
        instance.register = MagicMock()
        instance.unregister = MagicMock()
        instance.discover = AsyncMock(return_value=[])
        instance.validate = AsyncMock(return_value=None)
        yield instance


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"EARN-E P1 ({MOCK_HOST})",
        data={CONF_HOST: MOCK_HOST, CONF_SERIAL: MOCK_SERIAL},
        unique_id=MOCK_SERIAL,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Patch async_setup_entry to avoid real setup in config flow tests."""
    with patch(
        "homeassistant.components.earn_e_p1.async_setup_entry", return_value=True
    ) as mock:
        yield mock
