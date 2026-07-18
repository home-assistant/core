"""Fixtures for energieleser integration tests."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import AsyncMock, patch

from energieleser import (
    GasleserDevice,
    StromleserOneDevice,
    WaermeleserDevice,
    WasserleserDevice,
)
import pytest

from homeassistant.components.energieleser.const import DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST

from tests.common import MockConfigEntry

STROMLESER_DEVICE_ID = "STROM_ONE_8529546829"
GASLESER_DEVICE_ID = "GAS_8530321017"
WAERMELESER_DEVICE_ID = "HEAT_0000000001"
WASSERLESER_DEVICE_ID = "WASSER_0499632826"

# Firmware version advertised in the mDNS TXT "version" property at discovery.
STROMLESER_SW_VERSION = "v1.4.22-31-g1658863"

STROMLESER_API_RESPONSE: dict = {
    "device_id": STROMLESER_DEVICE_ID,
    "timestamp": "1776178480",
    "1.8.0": "12345.000 Wh",
    "2.8.0": "26561.000 Wh",
    "16.7.0": "8.160 W",
    "36.7.0": "0.000 W",
    "56.7.0": "0.000 W",
    "76.7.0": "8.160 W",
    "rssi": "-51",
}

GASLESER_API_RESPONSE: dict = {
    "device_id": GASLESER_DEVICE_ID,
    "timestamp": "1776179005",
    "count": 603,
    "total_consumption": 37030.67,
    "current_flow_rate": 0.01,
    "rssi": "-51",
}

WAERMELESER_API_RESPONSE: dict = {
    "device_id": WAERMELESER_DEVICE_ID,
    "timestamp": 1747285200,
    "total_energy_t1": "34.09 MWh",
    "total_energy_t2": "12.45 MWh",
    "total_energy_t3": "5.67 MWh",
    "power": "2.31 kW",
    "total_volume": "3561.23 m³",
    "volume_flow": "1.23 l/h",
    "flow_temperature": "16.90 °C",
    "return_temperature": "19.60 °C",
    "temperature_difference": "2.68 K",
    "fabrication_number": "17580352",
    "rssi": "-51",
}

WASSERLESER_API_RESPONSE: dict = {
    "device_id": WASSERLESER_DEVICE_ID,
    "timestamp": "1779276532",
    "total_consumption": "123.755 m3",
    "today_consumption": "0.000 m3",
    "current_flow_rate": "0 l/h",
    "current_flow_rate_m3": "0.0000 m3/h",
    "signal_strength": "-49 dBm",
}


@pytest.fixture
def mock_stromleser_device() -> StromleserOneDevice:
    """Return a parsed stromleser device built from the API fixture."""
    return StromleserOneDevice.from_payload(STROMLESER_API_RESPONSE)


@pytest.fixture
def mock_locked_stromleser_device(
    mock_stromleser_device: StromleserOneDevice,
) -> StromleserOneDevice:
    """Return a stromleser device with PIN locked."""
    return replace(mock_stromleser_device, pin_locked=True)


@pytest.fixture
def mock_gasleser_device() -> GasleserDevice:
    """Return a parsed gasleser device built from the API fixture."""
    return GasleserDevice.from_payload(GASLESER_API_RESPONSE)


@pytest.fixture
def mock_waermeleser_device() -> WaermeleserDevice:
    """Return a parsed wärmeleser device built from the API fixture."""
    return WaermeleserDevice.from_payload(WAERMELESER_API_RESPONSE)


@pytest.fixture
def mock_wasserleser_device() -> WasserleserDevice:
    """Return a parsed wasserleser device built from the API fixture."""
    return WasserleserDevice.from_payload(WASSERLESER_API_RESPONSE)


@pytest.fixture
def mock_stromleser_config_entry() -> MockConfigEntry:
    """Return a mocked config entry for a stromleser device."""
    return MockConfigEntry(
        title=STROMLESER_DEVICE_ID,
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_DEVICE_ID: STROMLESER_DEVICE_ID,
        },
        unique_id=STROMLESER_DEVICE_ID,
    )


@pytest.fixture
def mock_gasleser_config_entry() -> MockConfigEntry:
    """Return a mocked config entry for a gasleser device."""
    return MockConfigEntry(
        title=GASLESER_DEVICE_ID,
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.101",
            CONF_DEVICE_ID: GASLESER_DEVICE_ID,
        },
        unique_id=GASLESER_DEVICE_ID,
    )


@pytest.fixture
def mock_waermeleser_config_entry() -> MockConfigEntry:
    """Return a mocked config entry for a wärmeleser device."""
    return MockConfigEntry(
        title=WAERMELESER_DEVICE_ID,
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.102",
            CONF_DEVICE_ID: WAERMELESER_DEVICE_ID,
        },
        unique_id=WAERMELESER_DEVICE_ID,
    )


@pytest.fixture
def mock_wasserleser_config_entry() -> MockConfigEntry:
    """Return a mocked config entry for a wasserleser device."""
    return MockConfigEntry(
        title=WASSERLESER_DEVICE_ID,
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.103",
            CONF_DEVICE_ID: WASSERLESER_DEVICE_ID,
        },
        unique_id=WASSERLESER_DEVICE_ID,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.energieleser.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_energieleser_client(
    mock_stromleser_device: StromleserOneDevice,
) -> Generator[AsyncMock]:
    """Patch EnergieleserClient at both import sites with a default stromleser device."""
    with (
        patch(
            "homeassistant.components.energieleser.EnergieleserClient",
            autospec=True,
        ) as init_client,
        patch(
            "homeassistant.components.energieleser.config_flow.EnergieleserClient",
            new=init_client,
        ),
    ):
        instance = init_client.return_value
        instance.get_device.return_value = mock_stromleser_device
        yield instance
