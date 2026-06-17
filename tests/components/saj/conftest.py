"""Fixtures for saj tests."""

from collections.abc import Generator
from dataclasses import dataclass
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.saj.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_SERIAL_NUMBER, MOCK_USER_INPUT_ETHERNET, MOCK_USER_INPUT_WIFI

from tests.common import MockConfigEntry


@dataclass(slots=True)
class PySajMocks:
    """Pysaj mocks shared across SAJ integration modules."""

    saj: MagicMock
    sensors: list[MagicMock]


@pytest.fixture
def mock_config_entry_ethernet(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry for ethernet."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="SAJ Solar Inverter",
        unique_id=MOCK_SERIAL_NUMBER,
        data=MOCK_USER_INPUT_ETHERNET,
        entry_id="saj_entry_ethernet",
    )


@pytest.fixture
def mock_config_entry_wifi(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry for wifi."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="SAJ Solar Inverter",
        unique_id=MOCK_SERIAL_NUMBER,
        data=MOCK_USER_INPUT_WIFI,
        entry_id="saj_entry_wifi",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock the setup entry."""
    with patch(
        "homeassistant.components.saj.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_pysaj() -> Generator[PySajMocks]:
    """Mock pysaj where Home Assistant's SAJ integration imports it.

    This fixture patches both config flow and runtime code so they share the
    same mocked SAJ instance and Sensors definition.
    """
    saj_instance = MagicMock()
    saj_instance.serialnumber = MOCK_SERIAL_NUMBER
    saj_instance.read = AsyncMock(return_value=True)

    sensors: list[MagicMock] = []
    for key, value, unit, per_day_basis, per_total_basis in (
        ("current_power", 5000.0, "W", False, False),
        ("today_yield", 25.5, "kWh", True, False),
    ):
        sensor = MagicMock()
        sensor.name = key
        sensor.key = key
        sensor.value = value
        sensor.unit = unit
        sensor.enabled = True
        sensor.per_day_basis = per_day_basis
        sensor.per_total_basis = per_total_basis
        sensor.date = date.today()
        sensors.append(sensor)

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
        patch(
            "homeassistant.components.saj.sensor.pysaj.SAJ",
            new=saj_cls,
        ),
        patch(
            "homeassistant.components.saj.pysaj.Sensors",
            autospec=True,
            return_value=sensors,
        ) as sensors_cls,
        patch(
            "homeassistant.components.saj.config_flow.pysaj.Sensors",
            new=sensors_cls,
        ),
        patch(
            "homeassistant.components.saj.sensor.pysaj.Sensors",
            new=sensors_cls,
        ),
    ):
        yield PySajMocks(saj=saj_instance, sensors=sensors)
