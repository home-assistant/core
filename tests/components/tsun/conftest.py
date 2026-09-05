"""Fixtures for the TSUN integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from tsun_local_api import DeviceInfo, LoggerMetadata, Telemetry

from homeassistant.components.tsun.const import CONF_LOGGER_SN, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry

LOGGER_SN = 1_234_567_890
HOST = "192.0.2.10"


@pytest.fixture
def telemetry() -> Telemetry:
    """Return representative TSOL-MP3000 telemetry."""
    values = {
        "ac_voltage": 230.1,
        "ac_current": 5.42,
        "ac_frequency": 50.01,
        "ac_power": 1200.0,
        "ac_energy_today": 3.2,
        "ac_energy_total": 450.5,
        "dc_power_total": 1280.0,
    }
    for number in range(1, 7):
        values.update(
            {
                f"pv{number}_voltage": 35.0,
                f"pv{number}_current": 6.0,
                f"pv{number}_power": 210.0,
                f"pv{number}_energy_today": 0.5,
                f"pv{number}_energy_total": 75.0,
            }
        )
    return Telemetry(
        values,
        DeviceInfo(
            logger_sn=LOGGER_SN,
            model="TITAN",
            protocol="1511",
            pv_count=6,
            inverter_serial_number="Y000000000000000",
            firmware_version="TEST_FIRMWARE",
            mac_address="00:11:22:33:44:55",
        ),
        duration_ms=250,
        blocks_ok=4,
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a TSUN config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="TITAN",
        data={CONF_HOST: HOST, CONF_PORT: 8899, CONF_LOGGER_SN: LOGGER_SN},
        unique_id=str(LOGGER_SN),
    )


@pytest.fixture
def mock_tsun_client(telemetry: Telemetry) -> Generator[AsyncMock]:
    """Mock the external TSUN communication client."""
    with (
        patch(
            "homeassistant.components.tsun.TsunClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.tsun.config_flow.TsunClient",
            new=mock_client,
        ),
        patch(
            "homeassistant.components.tsun.config_flow.async_read_logger_metadata",
            return_value=LoggerMetadata(
                logger_sn=LOGGER_SN,
                inverter_serial_number="Y000000000000000",
                firmware_version="TEST_FIRMWARE",
                mac_address="00:11:22:33:44:55",
            ),
        ),
    ):
        client = mock_client.return_value
        client.async_read.return_value = telemetry
        client.diagnostic_trace = []
        yield client
