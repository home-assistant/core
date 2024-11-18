"""Fixtures for the System Monitor integration."""

from __future__ import annotations

from collections.abc import Generator
import socket
from unittest.mock import AsyncMock, Mock, NonCallableMock, patch

from psutil import NoSuchProcess, Process
from psutil._common import sdiskpart, sdiskusage, shwtemp, snetio, snicaddr, sswap
import pytest

from homeassistant.components.systemmonitor.const import DOMAIN
from homeassistant.components.systemmonitor.coordinator import VirtualMemory
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_sys_platform() -> Generator[None]:
    """Mock sys platform to Linux."""
    with patch("sys.platform", "linux"):
        yield


class MockProcess(Process):
    """Mock a Process class."""

    def __init__(self, name: str, ex: bool = False) -> None:
        """Initialize the process."""
        super().__init__(1)
        self._name = name
        self._ex = ex
        self._create_time = 1708700400

    def name(self):
        """Return a name."""
        if self._ex:
            raise NoSuchProcess(1, self._name)
        return self._name


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setup entry."""
    with patch(
        "homeassistant.components.systemmonitor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock ConfigEntry."""
    return MockConfigEntry(
        title="System Monitor",
        domain=DOMAIN,
        data={},
        options={
            "binary_sensor": {"process": ["python3", "pip"]},
            "resources": [
                "disk_use_percent_/",
                "disk_use_percent_/home/notexist/",
                "memory_free_",
                "network_out_eth0",
                "process_python3",
            ],
        },
    )


@pytest.fixture
async def mock_added_config_entry(
    hass: HomeAssistant,
    mock_psutil: Mock,
    mock_os: Mock,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Mock ConfigEntry that's been added to HA."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN in hass.config_entries.async_domains()
    return mock_config_entry


@pytest.fixture
def mock_process() -> list[MockProcess]:
    """Mock process."""
    _process_python = MockProcess("python3")
    _process_pip = MockProcess("pip")
    return [_process_python, _process_pip]


@pytest.fixture
def mock_psutil(mock_process: list[MockProcess]) -> Generator:
    """Mock psutil."""
    with patch(
        "homeassistant.components.systemmonitor.ha_psutil.PsutilWrapper",
    ) as psutil_wrapper:
        _wrapper = psutil_wrapper.return_value
        _wrapper.psutil = NonCallableMock()
        mock_psutil = _wrapper.psutil
        mock_psutil.disk_usage.return_value = sdiskusage(
            500 * 1024**3, 300 * 1024**3, 200 * 1024**3, 60.0
        )
        mock_psutil.swap_memory.return_value = sswap(
            100 * 1024**2, 60 * 1024**2, 40 * 1024**2, 60.0, 1, 1
        )
        mock_psutil.virtual_memory.return_value = VirtualMemory(
            100 * 1024**2,
            40 * 1024**2,
            40.0,
            60 * 1024**2,
            30 * 1024**2,
        )
        mock_psutil.net_io_counters.return_value = {
            "eth0": snetio(100 * 1024**2, 100 * 1024**2, 50, 50, 0, 0, 0, 0),
            "eth1": snetio(200 * 1024**2, 200 * 1024**2, 150, 150, 0, 0, 0, 0),
            "vethxyzxyz": snetio(300 * 1024**2, 300 * 1024**2, 150, 150, 0, 0, 0, 0),
        }
        mock_psutil.net_if_addrs.return_value = {
            "eth0": [
                snicaddr(
                    socket.AF_INET,
                    "192.168.1.1",
                    "255.255.255.0",
                    "255.255.255.255",
                    None,
                ),
                snicaddr(
                    socket.AF_INET6,
                    "fe80::baf2:8a90:4f78:b1cb%end0",
                    "ffff:ffff:ffff:ffff::",
                    None,
                    None,
                ),
                snicaddr(
                    socket.AF_INET6,
                    "2a00:1f:2103:3a01:3333:2222:1111:0000",
                    "ffff:ffff:ffff:ffff::",
                    None,
                    None,
                ),
            ],
            "eth1": [
                snicaddr(
                    socket.AF_INET,
                    "192.168.10.1",
                    "255.255.255.0",
                    "255.255.255.255",
                    None,
                )
            ],
            "vethxyzxyz": [
                snicaddr(
                    socket.AF_INET,
                    "172.16.10.1",
                    "255.255.255.0",
                    "255.255.255.255",
                    None,
                )
            ],
        }
        mock_psutil.cpu_percent.return_value = 10.0
        mock_psutil.boot_time.return_value = 1703973338.0
        mock_psutil.process_iter.return_value = mock_process
        # sensors_temperatures not available on MacOS so we
        # need to override the spec
        mock_psutil.sensors_temperatures = Mock()
        mock_psutil.sensors_temperatures.return_value = {
            "cpu0-thermal": [shwtemp("cpu0-thermal", 50.0, 60.0, 70.0)]
        }
        mock_psutil.disk_partitions.return_value = [
            sdiskpart("test", "/", "ext4", ""),
            sdiskpart("test2", "/media/share", "ext4", ""),
            sdiskpart("test3", "/incorrect", "", ""),
            sdiskpart("hosts", "/etc/hosts", "bind", ""),
            sdiskpart("proc", "/proc/run", "proc", ""),
        ]
        mock_psutil.boot_time.return_value = 1708786800.0
        mock_psutil.NoSuchProcess = NoSuchProcess
        yield mock_psutil


@pytest.fixture
def mock_os() -> Generator:
    """Mock os."""

    def isdir(path: str) -> bool:
        """Mock os.path.isdir."""
        return path != "/etc/hosts"

    with (
        patch("homeassistant.components.systemmonitor.coordinator.os") as mock_os,
        patch("homeassistant.components.systemmonitor.util.os") as mock_os_util,
    ):
        mock_os_util.name = "nt"
        mock_os.getloadavg.return_value = (1, 2, 3)
        mock_os_util.path.isdir = isdir
        yield mock_os
