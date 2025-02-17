"""ThermoPro session fixtures."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from thermopro_ble import ThermoProDevice

from homeassistant.util.dt import now


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def dummy_thermoprodevice(monkeypatch: pytest.MonkeyPatch) -> ThermoProDevice:
    """Mock for downstream library."""
    client = ThermoProDevice("")
    monkeypatch.setattr(client, "set_datetime", AsyncMock())
    return client


@pytest.fixture
def mock_thermoprodevice(
    monkeypatch: pytest.MonkeyPatch, dummy_thermoprodevice: ThermoProDevice
) -> ThermoProDevice:
    """Return downstream library mock."""
    monkeypatch.setattr(
        "homeassistant.components.thermopro.button.ThermoProDevice",
        MagicMock(return_value=dummy_thermoprodevice),
    )

    return dummy_thermoprodevice


@pytest.fixture
def mock_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Return fixed datetime for comparison."""
    fixed_now = now()

    monkeypatch.setattr(
        "homeassistant.components.thermopro.button.now",
        MagicMock(return_value=fixed_now),
    )

    return fixed_now
