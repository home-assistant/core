"""Common fixtures for the guntamatic tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.guntamatic.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

MOCK_DATA = {
    "Boiler temperature": ["14.09", "°C"],
    "Outdoor temperature": ["15.95", "°C"],
    "Buffer load": ["22", "%"],
    "Program": ["HEAT", ""],
    "Status": ["Service Ign.", ""],
    "Serial": ["959103", ""],
    "Version": ["32a", ""],
}

MOCK_PARSE_DATA = {
    "boiler_temperature": ["14.09", "°C"],
    "outdoor_temperature": ["15.95", "°C"],
    "buffer_load": ["22", "%"],
    "program": ["heat", ""],
    "status": ["Service Ign.", ""],
    "serial": ["959103", ""],
    "version": ["32a", ""],
    "heating_circulation_pump_1": ["auto", ""],
    "heating_circulation_program_1": ["heat", ""],
    "auxiliary_pump_0": ["nonstop", ""],
    "auxiliary_pump_1": ["auto", ""],
    "room_1_temperature": ["21.50", "°C"],
    "circuit_1_temp": ["55.00", "°C"],
    "operating_time": ["1188", "h"],
    "service_days": ["2012", "d"],
    "interruption_1": ["", ""],
    "interruption_2": ["", ""],
    "extra_dhw_0_temperature": ["53.00", "°C"],
    "extra_dhw_1_temperature": ["52.10", "°C"],
    "extra_dhw_2_temperature": ["51.80", "°C"],
    "extra_dhw_boost_0": ["auto", ""],
    "extra_dhw_boost_1": ["off", ""],
    "buffer_top_temperature": ["65.40", "°C"],
    "buffer_top_0_temperature": ["64.10", "°C"],
    "buffer_center_temperature": ["58.20", "°C"],
    "buffer_bottom_temperature": ["45.30", "°C"],
    "buffer_bottom_0_temperature": ["44.80", "°C"],
    "boiler_shunt_pump": ["45", "%"],
    "suction_fan": ["78", "%"],
    "primary_air": ["60", "%"],
    "secondary_air": ["35", "%"],
    "co2_content": ["12", "%"],
    "dhw_pump_0": ["30", "%"],
    "dhw_pump_1": ["25", "%"],
}


@pytest.fixture
def mock_heater() -> Generator[MagicMock]:
    """Mock the Heater class."""
    with (
        patch(
            "homeassistant.components.guntamatic.coordinator.Heater",
            autospec=True,
        ) as mock,
        patch("homeassistant.components.guntamatic.config_flow.Heater", new=mock),
    ):
        instance = mock.return_value
        instance.parse_data.return_value = MOCK_PARSE_DATA
        instance.host = "1.1.1.1"
        yield instance


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1"},
        unique_id=MOCK_DATA["Serial"][0],
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.guntamatic.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
