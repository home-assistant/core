"""Common fixtures for Sharp COCORO Air tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiosharp_cocoro_air import Device, DeviceProperties
import pytest

from homeassistant.components.sharp_cocoro_air.const import DOMAIN

from .const import CONFIG_INPUT

from tests.common import MockConfigEntry

DEVICE_1 = Device(
    box_id="box1",
    device_id="dev1",
    name="Living Room Purifier",
    echonet_node="node1",
    echonet_object="obj1",
    maker="Sharp",
    model="KC-G50",
    properties=DeviceProperties(
        power="on",
        temperature_c=22,
        humidity_pct=45,
        power_watts=25,
        energy_wh=1500,
        dust=3,
        smell=1,
        pci_sensor=50,
        light_sensor=80,
        filter_usage=1200,
        operation_mode="Auto",
        humidify=True,
        cleaning_mode="Cleaning + Humidifying",
        airflow="Medium",
    ),
)

DEVICE_2 = Device(
    box_id="box2",
    device_id="dev2",
    name="Bedroom Purifier",
    echonet_node="node2",
    echonet_object="obj2",
    maker="Sharp",
    model="KI-GS70",
    properties=DeviceProperties(power="off"),
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT,
        unique_id="test@example.com",
        entry_id="01JTEST00000000000000000",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry for config flow tests."""
    with patch(
        "homeassistant.components.sharp_cocoro_air.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_sharp_api() -> Generator[AsyncMock]:
    """Mock the SharpCOCOROAir client at the coordinator import path."""
    with patch(
        "homeassistant.components.sharp_cocoro_air.coordinator.SharpCOCOROAir",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.authenticate = AsyncMock()
        client.get_devices = AsyncMock(return_value=[DEVICE_1, DEVICE_2])
        client.power_on = AsyncMock()
        client.power_off = AsyncMock()
        client.set_mode = AsyncMock()
        client.set_humidify = AsyncMock()
        client.close = AsyncMock()
        yield client


@pytest.fixture
def mock_sharp_config_flow() -> Generator[AsyncMock]:
    """Mock the SharpCOCOROAir client at the config_flow import path."""
    with patch(
        "homeassistant.components.sharp_cocoro_air.config_flow.SharpCOCOROAir",
    ) as mock_cls:
        client = AsyncMock()
        client.authenticate = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        yield client
