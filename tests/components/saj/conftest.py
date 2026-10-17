"""Fixtures for saj tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.saj.const import DOMAIN

from . import MOCK_SERIAL_NUMBER, MOCK_USER_INPUT_ETHERNET, MOCK_USER_INPUT_WIFI

from tests.common import MockConfigEntry


@pytest.fixture
def connection_method(request: pytest.FixtureRequest) -> str:
    """Connection method for the config entry fixture."""
    return getattr(request, "param", "ethernet")


@pytest.fixture
def config_entry_data(connection_method: str) -> dict[str, Any]:
    """Return config entry data for the connection method."""
    if connection_method == "ethernet":
        return MOCK_USER_INPUT_ETHERNET
    return MOCK_USER_INPUT_WIFI


@pytest.fixture
def mock_config_entry(
    config_entry_data: dict[str, Any],
    connection_method: str,
) -> MockConfigEntry:
    """Return a mocked config entry for the selected connection method."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="SAJ Solar Inverter",
        unique_id=MOCK_SERIAL_NUMBER,
        data=config_entry_data,
        entry_id=f"saj_entry_{connection_method}",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock the setup entry."""
    with patch(
        "homeassistant.components.saj.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_pysaj_sensors() -> Generator[list[MagicMock]]:
    """Mock pysaj.Sensors across SAJ integration modules."""
    sensors: list[MagicMock] = []
    for key, value, unit in (
        ("current_power", 5000.0, "W"),
        ("today_yield", 25.5, "kWh"),
    ):
        sensor = MagicMock()
        sensor.name = key
        sensor.key = key
        sensor.value = value
        sensor.unit = unit
        sensor.enabled = True
        sensors.append(sensor)

    with (
        patch(
            "homeassistant.components.saj.pysaj.Sensors",
            autospec=True,
            return_value=sensors,
        ) as sensors_cls,
        patch(
            "homeassistant.components.saj.config_flow.pysaj.Sensors",
            new=sensors_cls,
        ),
    ):
        yield sensors


@pytest.fixture
def mock_pysaj_saj(mock_pysaj_sensors: list[MagicMock]) -> Generator[MagicMock]:
    """Mock pysaj.SAJ across SAJ integration modules."""
    saj_instance = MagicMock()
    saj_instance.serialnumber = MOCK_SERIAL_NUMBER
    saj_instance.read = AsyncMock(return_value=True)

    with (
        patch(
            "homeassistant.components.saj.pysaj.SAJ",
            autospec=True,
            return_value=saj_instance,
        ) as saj_cls,
        patch(
            "homeassistant.components.saj.config_flow.pysaj.SAJ",
            new=saj_cls,
        ),
    ):
        yield saj_instance
