"""Common fixtures for the Probe Plus tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from pyprobeplus.parsers.base import ProbePlusData, ProbeReading
import pytest

from homeassistant.components.probe_plus.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.probe_plus.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="FM210 aa:bb:cc:dd:ee:ff",
        domain=DOMAIN,
        version=1,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_MODEL: "FM210",
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )


@pytest.fixture
def mock_probe_reading() -> MagicMock:
    """Return a mock probe reading."""
    probe = create_autospec(ProbeReading, instance=True)
    probe.temperature = 25.0
    probe.rssi = -60
    probe.voltage = 3.7
    probe.online = True
    return probe


@pytest.fixture
def mock_probe_plus() -> Generator[MagicMock]:
    """Mock the Probe Plus device with multiple probes."""
    with patch(
        "homeassistant.components.probe_plus.coordinator.ProbePlusDevice",
        autospec=True,
    ) as mock_device:
        device = mock_device.return_value
        device.connected = True
        device.mac = "aa:bb:cc:dd:ee:ff"
        device.name = "FM210"
        device.connect = AsyncMock()
        device.device_disconnected_handler = MagicMock()

        probe_1 = create_autospec(ProbeReading, instance=True)
        probe_1.temperature = 25.0
        probe_1.rssi = -60
        probe_1.voltage = 3.7
        probe_1.online = True
        probe_1.battery = 75

        probe_2 = create_autospec(ProbeReading, instance=True)
        probe_2.temperature = 22.0
        probe_2.rssi = -70
        probe_2.voltage = 3.8
        probe_2.online = True
        probe_2.battery = 80

        device_state = create_autospec(ProbePlusData, instance=True)
        device_state.relay_voltage = 10.5
        device_state.relay_status = 1
        device_state.relay_battery = 100
        device_state.alarm_temperatures = None
        device_state.cook_targets = [None, None]
        device_state.probes = [probe_1, probe_2]

        device.device_state = device_state
        yield device
