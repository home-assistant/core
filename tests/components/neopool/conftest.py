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
    "Hydrolysis module detected": True,
    "Redox measurement module detected": True,
    "pH measurement module detected": True,
    "MBF_PAR_FILT_MODE": 0,
    "filtration_mode": "manual",
    "filtration_speed_state": "off",
    "MBF_MEASURE_TEMPERATURE": 250,
    "MBF_MEASURE_PH": 720,
    "Filtration Pump": False,
    "MBF_PAR_HIDRO_COVER_REDUCTION": 0x0C19,
    "Pool Cover": 0,
    "relay_light_enable": 4,
    "relay_aux1_enable": 4,
    "relay_aux2_enable": 4,
    "relay_aux3_enable": 4,
    "relay_aux4_enable": 4,
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
    """Return a config entry with every optional feature toggle enabled.

    Keeping every option turned on by default means a single fixture covers
    the entity-discovery happy path for every platform; tests that need a
    leaner setup can override `options` per-test.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=f"neopool_{MOCK_SERIAL}",
        version=CURRENT_VERSION,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_NAME: MOCK_NAME,
            "unit_id": DEFAULT_UNIT_ID,
            "modbus_framer": "tcp",
        },
        options={
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
            "homeassistant.components.neopool.config_flow.async_get_device_serial",
            new=AsyncMock(return_value=MOCK_SERIAL),
        ),
    ):
        mock_client = mock_client_cls.return_value
        mock_client.async_read_all = AsyncMock(return_value=dict(MOCK_POOL_DATA))
        mock_client.read_all_timers = AsyncMock(return_value={})
        mock_client.async_write_register = AsyncMock(
            return_value={"value": 0, "confirmed": 0}
        )
        mock_client.async_set_filtration_mode = AsyncMock(return_value=None)
        mock_client.async_set_cell_boost = AsyncMock(return_value=None)
        mock_client.async_set_filtration_speed = AsyncMock(return_value=None)
        mock_client.async_set_temp_setpoint = AsyncMock(return_value=None)
        mock_client.async_sync_device_time = AsyncMock(return_value=None)
        mock_client.async_clear_errors = AsyncMock(return_value=None)
        mock_client.async_reset_user_counters = AsyncMock(return_value=None)
        mock_client.write_timer = AsyncMock()
        mock_client.close = AsyncMock()
        yield mock_client


@pytest.fixture
def minimal_pool_data() -> dict[str, Any]:
    """Pool data with all optional capability flags off.

    Used to drive the 'should-skip' branches in every platform that
    suppress entities when the corresponding module / relay is absent.
    Hardcoded copy rather than a dict subtraction so the suppressed
    state is explicit at the call site.
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
def mock_neopool_client_minimal(
    minimal_pool_data: dict[str, Any],
) -> Generator[MagicMock]:
    """Like mock_neopool_client but seeded with minimal_pool_data.

    Use to exercise platform 'skip-because-disabled' branches.
    """
    with (
        patch(
            "homeassistant.components.neopool.NeoPoolModbusClient",
            autospec=True,
        ) as mock_client_cls,
        patch(
            "homeassistant.components.neopool.config_flow.async_get_device_serial",
            new=AsyncMock(return_value=MOCK_SERIAL),
        ),
    ):
        mock_client = mock_client_cls.return_value
        mock_client.async_read_all = AsyncMock(return_value=dict(minimal_pool_data))
        mock_client.read_all_timers = AsyncMock(return_value={})
        mock_client.async_write_register = AsyncMock(
            return_value={"value": 0, "confirmed": 0}
        )
        mock_client.write_timer = AsyncMock()
        mock_client.close = AsyncMock()
        yield mock_client


@pytest.fixture
def mock_socket_connection() -> Generator[None]:
    """Patch the TCP probe in config_flow so we don't hit the network.

    Not autouse, opt in via the fixture name when the integration's
    config-flow setup runs in the test (it would otherwise try to open
    a real TCP connection).
    """
    with patch(
        "homeassistant.components.neopool.config_flow.is_host_port_open",
        new=AsyncMock(return_value=True),
    ):
        yield
