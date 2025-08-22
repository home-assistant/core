"""Test fixtures for the Seko PoolDose integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pooldose.request_status import RequestStatus
import pytest

from homeassistant.components.pooldose.const import DOMAIN
from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

SERIAL_NUMBER = "SN123456789"


@pytest.fixture
def mock_pooldose_client() -> Generator[MagicMock]:
    """Mock a PooldoseClient."""
    with (
        patch(
            "homeassistant.components.pooldose.coordinator.PooldoseClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient",
            new=mock_client,
        ),
        patch(
            "homeassistant.components.pooldose.PooldoseClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.device_info = {
            "identifiers": {("pooldose", SERIAL_NUMBER)},
            "name": "PoolDose Device",
            "manufacturer": "SEKO",
            "model": "PDPR1H1HAW100",
            "serial_number": SERIAL_NUMBER,
            "sw_version": "1.5",
            "hw_version": "FW539187",
            "API_VERSION": "v1/",
            "MAC": "AA:BB:CC:DD:EE:FF",
            "IP": "192.168.1.100",
        }
        client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
        client.check_apiversion_supported = MagicMock(
            return_value=(RequestStatus.SUCCESS, {})
        )
        client.instant_values = AsyncMock(
            return_value=(RequestStatus.SUCCESS, {"temperature": [25.5, "°C"]})
        )
        client.available_sensors = MagicMock(return_value=["temperature", "ph", "orp"])
        client.is_connected = True
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="PoolDose Device",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id=SERIAL_NUMBER,
    )


@pytest.fixture
def mock_device_info(mock_pooldose_client) -> dict[str, str]:
    """Return mock device info from the client."""
    return mock_pooldose_client.device_info


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Return a mocked coordinator with realistic data."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {
        "temperature": [25.5, "°C"],
        "ph": [7.2, "pH"],
        "orp": [650, "mV"],
        "ph_type_dosing": ["Automatic", ""],
        "peristaltic_ph_dosing": [15, "ml/min"],
        "orp_type_dosing": ["Manual", ""],
        "peristaltic_orp_dosing": [10, "ml/min"],
        "ph_calibration_type": ["3-point", ""],
        "ph_calibration_offset": [0.5, "mV"],
        "ph_calibration_slope": [98.5, "%"],
        "orp_calibration_type": ["2-point", ""],
        "orp_calibration_offset": [-5, "mV"],
        "orp_calibration_slope": [102.1, "%"],
        "ofa_ph_value": [30, "min"],
    }
    coordinator.last_update_success = True
    return coordinator


@pytest.fixture
def mock_coordinator_empty() -> MagicMock:
    """Return a mocked coordinator with empty data."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {}
    coordinator.last_update_success = True
    return coordinator


@pytest.fixture
def mock_instant_values() -> dict:
    """Return realistic instant values data structure."""
    return {
        "deviceInfo": {"dwi_status": "ok", "modbus_status": "on"},
        "collapsed_bar": [],
        "PDPR1H1HAW100_FW539187_w_1ekeigkin": {
            "visible": True,
            "alarm": False,
            "current": 7.6,
            "resolution": 0.1,
            "magnitude": ["pH", "PH"],
            "absMin": 0,
            "absMax": 14,
            "minT": 6,
            "maxT": 8,
        },
        "PDPR1H1HAW100_FW539187_w_1eklenb23": {
            "visible": True,
            "alarm": False,
            "current": 707,
            "resolution": 1,
            "magnitude": ["mV", "MV"],
            "absMin": -99,
            "absMax": 999,
            "minT": 600,
            "maxT": 800,
        },
        "PDPR1H1HAW100_FW539187_w_1eommf39k": {
            "visible": True,
            "alarm": False,
            "current": 29.5,
            "resolution": 0.1,
            "magnitude": ["°C", "CDEG"],
            "absMin": 0,
            "absMax": 55,
            "minT": 10,
            "maxT": 38,
        },
    }
