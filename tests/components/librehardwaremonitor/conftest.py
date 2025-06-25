"""Common fixtures for the LibreHardwareMonitor tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from librehardwaremonitor_api.model import (
    LibreHardwareMonitorData,
    LibreHardwareMonitorSensorData,
)
import pytest

from homeassistant.components.librehardwaremonitor.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry

VALID_CONFIG = {CONF_HOST: "192.168.0.20", CONF_PORT: 8085}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.librehardwaremonitor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Config entry fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.20:8085",
        unique_id="192.168.0.20:8085",
        data=VALID_CONFIG,
    )


@pytest.fixture
def mock_lhm_client() -> Generator[AsyncMock]:
    """Mock a LibreHardwareMonitor client."""
    with (
        patch(
            "homeassistant.components.librehardwaremonitor.config_flow.LibreHardwareMonitorClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.librehardwaremonitor.coordinator.LibreHardwareMonitorClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_data.return_value = LHM_SAMPLE_DATA

        yield client


LHM_SAMPLE_DATA = LibreHardwareMonitorData(
    main_device_names=[
        "MSI MAG B650M MORTAR WIFI (MS-7D76)",
        "AMD Ryzen 7 7800X3D",
        "NVIDIA GeForce RTX 4080 SUPER",
    ],
    sensor_data={
        "lpc-nct6687d-0-voltage-0": LibreHardwareMonitorSensorData(
            name="+12V Voltage",
            value="12,072",
            min="12,072",
            max="12,096",
            unit="V",
            device_id="lpc-nct6687d",
            device_name="MSI MAG B650M MORTAR WIFI (MS-7D76)",
            device_type="MAINBOARD",
            sensor_id="lpc-nct6687d-0-voltage-0",
        ),
        "lpc-nct6687d-0-voltage-1": LibreHardwareMonitorSensorData(
            name="+5V Voltage",
            value="5,050",
            min="5,050",
            max="5,060",
            unit="V",
            device_id="lpc-nct6687d",
            device_name="MSI MAG B650M MORTAR WIFI (MS-7D76)",
            device_type="MAINBOARD",
            sensor_id="lpc-nct6687d-0-voltage-1",
        ),
        "lpc-nct6687d-0-voltage-2": LibreHardwareMonitorSensorData(
            name="Vcore Voltage",
            value="1,314",
            min="1,314",
            max="1,316",
            unit="V",
            device_id="lpc-nct6687d",
            device_name="MSI MAG B650M MORTAR WIFI (MS-7D76)",
            device_type="MAINBOARD",
            sensor_id="lpc-nct6687d-0-voltage-2",
        ),
        "lpc-nct6687d-0-temperature-0": LibreHardwareMonitorSensorData(
            name="CPU Temperature",
            value="42,0",
            min="40,0",
            max="62,0",
            unit="°C",
            device_id="lpc-nct6687d",
            device_name="MSI MAG B650M MORTAR WIFI (MS-7D76)",
            device_type="MAINBOARD",
            sensor_id="lpc-nct6687d-0-temperature-0",
        ),
        "lpc-nct6687d-0-temperature-1": LibreHardwareMonitorSensorData(
            name="System Temperature",
            value="31,5",
            min="30,5",
            max="31,5",
            unit="°C",
            device_id="lpc-nct6687d",
            device_name="MSI MAG B650M MORTAR WIFI (MS-7D76)",
            device_type="MAINBOARD",
            sensor_id="lpc-nct6687d-0-temperature-1",
        ),
        "lpc-nct6687d-0-fan-0": LibreHardwareMonitorSensorData(
            name="CPU Fan Fan",
            value="0",
            min="0",
            max="0",
            unit="RPM",
            device_id="lpc-nct6687d",
            device_name="MSI MAG B650M MORTAR WIFI (MS-7D76)",
            device_type="MAINBOARD",
            sensor_id="lpc-nct6687d-0-fan-0",
        ),
        "lpc-nct6687d-0-fan-1": LibreHardwareMonitorSensorData(
            name="Pump Fan Fan",
            value="0",
            min="0",
            max="0",
            unit="RPM",
            device_id="lpc-nct6687d",
            device_name="MSI MAG B650M MORTAR WIFI (MS-7D76)",
            device_type="MAINBOARD",
            sensor_id="lpc-nct6687d-0-fan-1",
        ),
        "lpc-nct6687d-0-fan-2": LibreHardwareMonitorSensorData(
            name="System Fan #1 Fan",
            value="-",
            min="-",
            max="-",
            unit=None,
            device_id="lpc-nct6687d",
            device_name="MSI MAG B650M MORTAR WIFI (MS-7D76)",
            device_type="MAINBOARD",
            sensor_id="lpc-nct6687d-0-fan-2",
        ),
        "amdcpu-0-voltage-2": LibreHardwareMonitorSensorData(
            name="VDDCR Voltage",
            value="1,081",
            min="0,519",
            max="1,162",
            unit="V",
            device_id="amdcpu-0",
            device_name="AMD Ryzen 7 7800X3D",
            device_type="CPU",
            sensor_id="amdcpu-0-voltage-2",
        ),
        "amdcpu-0-voltage-3": LibreHardwareMonitorSensorData(
            name="VDDCR SoC Voltage",
            value="1,305",
            min="1,305",
            max="1,305",
            unit="V",
            device_id="amdcpu-0",
            device_name="AMD Ryzen 7 7800X3D",
            device_type="CPU",
            sensor_id="amdcpu-0-voltage-3",
        ),
        "amdcpu-0-power-0": LibreHardwareMonitorSensorData(
            name="Package Power",
            value="31,0",
            min="30,7",
            max="46,6",
            unit="W",
            device_id="amdcpu-0",
            device_name="AMD Ryzen 7 7800X3D",
            device_type="CPU",
            sensor_id="amdcpu-0-power-0",
        ),
        "amdcpu-0-temperature-2": LibreHardwareMonitorSensorData(
            name="Core (Tctl/Tdie) Temperature",
            value="41,9",
            min="40,6",
            max="62,8",
            unit="°C",
            device_id="amdcpu-0",
            device_name="AMD Ryzen 7 7800X3D",
            device_type="CPU",
            sensor_id="amdcpu-0-temperature-2",
        ),
        "amdcpu-0-temperature-3": LibreHardwareMonitorSensorData(
            name="Package Temperature",
            value="39,4",
            min="37,4",
            max="73,0",
            unit="°C",
            device_id="amdcpu-0",
            device_name="AMD Ryzen 7 7800X3D",
            device_type="CPU",
            sensor_id="amdcpu-0-temperature-3",
        ),
        "amdcpu-0-load-0": LibreHardwareMonitorSensorData(
            name="CPU Total Load",
            value="0,9",
            min="0,0",
            max="15,9",
            unit="%",
            device_id="amdcpu-0",
            device_name="AMD Ryzen 7 7800X3D",
            device_type="CPU",
            sensor_id="amdcpu-0-load-0",
        ),
        "gpu-nvidia-0-power-0": LibreHardwareMonitorSensorData(
            name="GPU Package Power",
            value="10,3",
            min="10,2",
            max="42,3",
            unit="W",
            device_id="gpu-nvidia-0",
            device_name="NVIDIA GeForce RTX 4080 SUPER",
            device_type="NVIDIA",
            sensor_id="gpu-nvidia-0-power-0",
        ),
        "gpu-nvidia-0-clock-0": LibreHardwareMonitorSensorData(
            name="GPU Core Clock",
            value="210,0",
            min="210,0",
            max="2550,0",
            unit="MHz",
            device_id="gpu-nvidia-0",
            device_name="NVIDIA GeForce RTX 4080 SUPER",
            device_type="NVIDIA",
            sensor_id="gpu-nvidia-0-clock-0",
        ),
        "gpu-nvidia-0-clock-4": LibreHardwareMonitorSensorData(
            name="GPU Memory Clock",
            value="405,0",
            min="405,0",
            max="11752,0",
            unit="MHz",
            device_id="gpu-nvidia-0",
            device_name="NVIDIA GeForce RTX 4080 SUPER",
            device_type="NVIDIA",
            sensor_id="gpu-nvidia-0-clock-4",
        ),
        "gpu-nvidia-0-temperature-0": LibreHardwareMonitorSensorData(
            name="GPU Core Temperature",
            value="23,0",
            min="23,0",
            max="25,0",
            unit="°C",
            device_id="gpu-nvidia-0",
            device_name="NVIDIA GeForce RTX 4080 SUPER",
            device_type="NVIDIA",
            sensor_id="gpu-nvidia-0-temperature-0",
        ),
        "gpu-nvidia-0-temperature-2": LibreHardwareMonitorSensorData(
            name="GPU Hot Spot Temperature",
            value="31,0",
            min="30,8",
            max="32,2",
            unit="°C",
            device_id="gpu-nvidia-0",
            device_name="NVIDIA GeForce RTX 4080 SUPER",
            device_type="NVIDIA",
            sensor_id="gpu-nvidia-0-temperature-2",
        ),
        "gpu-nvidia-0-load-0": LibreHardwareMonitorSensorData(
            name="GPU Core Load",
            value="0,0",
            min="0,0",
            max="2,0",
            unit="%",
            device_id="gpu-nvidia-0",
            device_name="NVIDIA GeForce RTX 4080 SUPER",
            device_type="NVIDIA",
            sensor_id="gpu-nvidia-0-load-0",
        ),
        "gpu-nvidia-0-load-1": LibreHardwareMonitorSensorData(
            name="GPU Memory Controller Load",
            value="0,0",
            min="0,0",
            max="1,0",
            unit="%",
            device_id="gpu-nvidia-0",
            device_name="NVIDIA GeForce RTX 4080 SUPER",
            device_type="NVIDIA",
            sensor_id="gpu-nvidia-0-load-1",
        ),
        "gpu-nvidia-0-load-2": LibreHardwareMonitorSensorData(
            name="GPU Video Engine Load",
            value="0,0",
            min="0,0",
            max="0,0",
            unit="%",
            device_id="gpu-nvidia-0",
            device_name="NVIDIA GeForce RTX 4080 SUPER",
            device_type="NVIDIA",
            sensor_id="gpu-nvidia-0-load-2",
        ),
        "gpu-nvidia-0-fan-1": LibreHardwareMonitorSensorData(
            name="GPU Fan 1 Fan",
            value="0",
            min="0",
            max="0",
            unit="RPM",
            device_id="gpu-nvidia-0",
            device_name="NVIDIA GeForce RTX 4080 SUPER",
            device_type="NVIDIA",
            sensor_id="gpu-nvidia-0-fan-1",
        ),
        "gpu-nvidia-0-fan-2": LibreHardwareMonitorSensorData(
            name="GPU Fan 2 Fan",
            value="0",
            min="0",
            max="0",
            unit="RPM",
            device_id="gpu-nvidia-0",
            device_name="NVIDIA GeForce RTX 4080 SUPER",
            device_type="NVIDIA",
            sensor_id="gpu-nvidia-0-fan-2",
        ),
        "gpu-nvidia-0-throughput-1": LibreHardwareMonitorSensorData(
            name="GPU PCIe Tx Throughput",
            value="50,0",
            min="50,0",
            max="300,0",
            unit="KB/s",
            device_id="gpu-nvidia-0",
            device_name="NVIDIA GeForce RTX 4080 SUPER",
            device_type="NVIDIA",
            sensor_id="gpu-nvidia-0-throughput-1",
        ),
    },
)
