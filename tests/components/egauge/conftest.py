"""Fixtures for eGauge integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from egauge_async.json.models import RegisterInfo, RegisterType
import pytest

from homeassistant.components.egauge.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="eGauge",
        domain=DOMAIN,
        data={
            CONF_HOST: "http://192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
        unique_id="ABC123456",
    )


@pytest.fixture(autouse=True)
def mock_egauge_client() -> Generator[MagicMock]:
    """Return a mocked eGauge client."""
    with (
        patch(
            "homeassistant.components.egauge.coordinator.EgaugeJsonClient",
            autospec=True,
        ) as mock_class,
        patch(
            "homeassistant.components.egauge.config_flow.EgaugeJsonClient",
            new=mock_class,
        ),
    ):
        client = mock_class.return_value

        # Static device info
        client.get_device_serial_number.return_value = "ABC123456"
        client.get_hostname.return_value = "egauge-home"
        client.get_register_info.return_value = {
            "Grid": RegisterInfo(name="Grid", type=RegisterType.POWER, idx=0, did=None),
            "Solar": RegisterInfo(
                name="Solar", type=RegisterType.POWER, idx=1, did=None
            ),
            # Include unsupported type to test graceful handling
            "Temp": RegisterInfo(
                name="Temp", type=RegisterType.TEMPERATURE, idx=2, did=None
            ),
            "L1": RegisterInfo(name="L1", type=RegisterType.VOLTAGE, idx=3, did=None),
        }

        # Dynamic measurements
        client.get_current_measurements.return_value = {
            "Grid": 1500.0,
            "Solar": -2500.0,
            "Temp": 45.0,
            "L1": 123.4,
        }
        client.get_current_counters.return_value = {
            "Grid": 450000000.0,  # 125 kWh in Ws
            "Solar": 315000000.0,  # 87.5 kWh in Ws
            "Temp": 0.0,
            "L1": 12345678.0,
        }

        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> MockConfigEntry:
    """Set up the eGauge integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
