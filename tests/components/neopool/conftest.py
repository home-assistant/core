"""Common fixtures for the NeoPool tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.neopool.const import (
    CURRENT_VERSION,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from tests.common import MockConfigEntry

MOCK_HOST = "192.0.2.1"
MOCK_PORT = DEFAULT_PORT
MOCK_NAME = "Pool"
MOCK_SERIAL = "1234567890"


MOCK_POOL_DATA: dict[str, Any] = {
    "MBF_POWER_MODULE_VERSION": 0x1234,
    "MBF_PAR_VERSION": 0x100,
    "MBF_PAR_MODEL": 0x0003,
    "MBF_PAR_SERNUM": int(MOCK_SERIAL),
    "MBF_PAR_FILTRATION_CONF": 1,
    "MBF_PAR_FILT_GPIO": 1,
    "MBF_PAR_LIGHTING_GPIO": 2,
    "MBF_PAR_HEATING_GPIO": 3,
    "MBF_PAR_PH_ACID_RELAY_GPIO": 4,
    "MBF_PAR_PH_BASE_RELAY_GPIO": 5,
    "MBF_PAR_RX_RELAY_GPIO": 6,
    "MBF_PAR_CL_RELAY_GPIO": 7,
    "MBF_PAR_CD_RELAY_GPIO": 0,
    "MBF_PAR_UV_RELAY_GPIO": 1,
    "MBF_PAR_FILTVALVE_GPIO": 1,
    "MBF_PAR_FILTVALVE_ENABLE": 1,
    "MBF_PAR_TEMPERATURE_ACTIVE": 1,
    "MBF_PAR_UICFG_MACHINE": 0,
    "MBF_PAR_RELAY_PH": 0,
    "Hydrolysis module detected": True,
    "Redox measurement module detected": True,
    "pH measurement module detected": True,
    "Chlorine measurement module detected": True,
    "Conductivity measurement module detected": True,
    "Ionization module detected": True,
    "MBF_PAR_FILT_MODE": 0,
    "filtration_mode": "manual",
    "filtration_speed_state": "off",
    "MBF_MEASURE_TEMPERATURE": 250,
    "MBF_MEASURE_PH": 720,
    "MBF_MEASURE_RX": 650,
    "MBF_MEASURE_CL": 120,
    "MBF_MEASURE_CONDUCTIVITY": 45,
    "MBF_HIDRO_CURRENT": 70,
    "MBF_HIDRO_VOLTAGE": 24,
    "MBF_ION_CURRENT": 50,
    "MBF_PAR_INTELLIGENT_INTERVALS": 4,
    "MBF_PAR_INTELLIGENT_TT_NEXT_INTERVAL": 7200,
    "MBF_PAR_FILTVALVE_REMAINING": 0,
    "HIDRO_POLARITY": 0,
    "ION_POLARITY": 0,
    "PH_PUMP_STATUS": "off",
    "HIDRO in Pol1": False,
    "HIDRO in Pol2": False,
    "HIDRO in dead time": False,
    "ION in Pol1": False,
    "ION in Pol2": False,
    "ION in dead time": False,
    "pH control module": True,
    "pH pump active": False,
    "pH acid pump active": False,
    "Filtration Pump": False,
    "MBF_PAR_HIDRO_COVER_REDUCTION": 0x0C19,
    "Pool Cover": 0,
    "CELL_RUNTIME_TOTAL": 0x00010000,
    "CELL_RUNTIME_PART": 0x00000E10,
    "CELL_RUNTIME_POLA": 0x00000708,
    "CELL_RUNTIME_POLB": 0x00000708,
    "CELL_RUNTIME_POL_CHANGES": 0x00000007,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.neopool.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry with a bare-serial unique_id."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_SERIAL,
        version=CURRENT_VERSION,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_NAME: MOCK_NAME,
            "unit_id": DEFAULT_UNIT_ID,
            "modbus_framer": "tcp",
        },
    )


@pytest.fixture
def mock_neopool_client() -> Generator[MagicMock]:
    """Patch the NeoPoolModbusClient and return a configurable mock instance."""
    with (
        patch(
            "homeassistant.components.neopool.NeoPoolModbusClient",
            autospec=True,
        ) as mock_client_cls,
        patch(
            "homeassistant.components.neopool.config_flow.async_probe_serial",
            new=AsyncMock(return_value=MOCK_SERIAL),
        ),
    ):
        mock_client = mock_client_cls.return_value
        mock_client.async_read_all = AsyncMock(return_value=dict(MOCK_POOL_DATA))
        mock_client.close = AsyncMock()
        yield mock_client


@pytest.fixture
def minimal_pool_data() -> dict[str, Any]:
    """Pool data with all optional capability flags off.

    Used to drive the 'should-skip' branches for supported_fn gating.
    """
    return {
        "MBF_POWER_MODULE_VERSION": 0x1234,
        "MBF_PAR_VERSION": 0x100,
        "MBF_PAR_MODEL": 0,
        "MBF_PAR_SERNUM": int(MOCK_SERIAL),
        "MBF_PAR_FILTRATION_CONF": 0,
        "MBF_PAR_FILT_GPIO": 0,
        "MBF_PAR_LIGHTING_GPIO": 0,
        "MBF_PAR_HEATING_GPIO": 0,
        "MBF_PAR_PH_ACID_RELAY_GPIO": 0,
        "MBF_PAR_PH_BASE_RELAY_GPIO": 0,
        "MBF_PAR_RX_RELAY_GPIO": 0,
        "MBF_PAR_CL_RELAY_GPIO": 0,
        "MBF_PAR_CD_RELAY_GPIO": 0,
        "MBF_PAR_UV_RELAY_GPIO": 0,
        "MBF_PAR_FILTVALVE_GPIO": 0,
        "MBF_PAR_FILTVALVE_ENABLE": 0,
        "MBF_PAR_TEMPERATURE_ACTIVE": 0,
        "Hydrolysis module detected": False,
        "Redox measurement module detected": False,
        "pH measurement module detected": False,
        "MBF_PAR_FILT_MODE": 0,
        "filtration_mode": "manual",
        "filtration_speed_state": "off",
        "Filtration Pump": False,
    }


@pytest.fixture
def mock_socket_connection() -> Generator[AsyncMock]:
    """Patch the lib probe in config_flow so we don't hit the network."""
    with patch(
        "homeassistant.components.neopool.config_flow.async_probe_serial",
        new=AsyncMock(return_value=MOCK_SERIAL),
    ) as mock:
        yield mock
