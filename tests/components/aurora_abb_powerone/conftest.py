"""Fixtures for Aurora ABB PowerOne tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.aurora_abb_powerone.aurora_client import (
    AuroraInverterData,
    AuroraInverterIdentifier,
)
from homeassistant.components.aurora_abb_powerone.const import (
    CONF_INVERTER_SERIAL_ADDRESS,
    CONF_SERIAL_COMPORT,
    CONF_TRANSPORT,
    DOMAIN,
    TRANSPORT_SERIAL,
)
from homeassistant.const import ATTR_SERIAL_NUMBER

from .const import MOCK_FIRMWARE, MOCK_MODEL, MOCK_SERIAL_NUMBER

from tests.common import MockConfigEntry

MOCK_INVERTER_IDENTIFIER = AuroraInverterIdentifier(
    serial_number=MOCK_SERIAL_NUMBER,
    model=MOCK_MODEL,
    firmware=MOCK_FIRMWARE,
)

MOCK_INVERTER_DATA = AuroraInverterData(
    grid_voltage=235.9,
    grid_current=2.8,
    instantaneouspower=45.7,
    grid_frequency=50.8,
    i_leak_dcdc=1.2345,
    i_leak_inverter=2.3456,
    power_in_1=12.3,
    power_in_2=23.5,
    temp=9.9,
    voltage_in_1=123.5,
    current_in_1=1.0,
    voltage_in_2=234.6,
    current_in_2=1.2,
    r_iso=0.1234,
    totalenergy=12.35,
    alarm="No alarm",
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TRANSPORT: TRANSPORT_SERIAL,
            CONF_INVERTER_SERIAL_ADDRESS: 3,
            CONF_SERIAL_COMPORT: "/dev/ttyUSB7",
            ATTR_SERIAL_NUMBER: MOCK_SERIAL_NUMBER,
            "model": MOCK_MODEL,
            "firmware": MOCK_FIRMWARE,
        },
        unique_id=MOCK_SERIAL_NUMBER,
        version=1,
        minor_version=2,
    )


@pytest.fixture
def mock_aurora_client() -> Generator[MagicMock]:
    """Return a mocked AuroraClient class."""
    with patch(
        "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraClient",
        autospec=True,
    ) as mock_client_class:
        mock_instance = MagicMock()
        mock_instance.try_connect_and_fetch_identifier.return_value = (
            MOCK_INVERTER_IDENTIFIER
        )
        mock_instance.try_connect_and_fetch_data.return_value = MOCK_INVERTER_DATA
        mock_client_class.from_serial.return_value = mock_instance
        mock_client_class.from_tcp.return_value = mock_instance
        yield mock_client_class
