"""Common fixtures for the ZhongHong tests."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, patch

import pytest
from zhong_hong_hvac.protocol import (
    AcAddr,
    AcStatus,
    FuncCode,
    StatusFanMode,
    StatusOperation,
    StatusSwitch,
)

from homeassistant.components.zhong_hong.const import (
    CONF_GATEWAY_ADDRESS,
    DEFAULT_GATEWAY_ADDRESS,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry

HOST = "1.2.3.4"
DEVICE_ADDRESS = (1, 1)
ENTITY_ID = "climate.ac_1_1"


def build_status(
    switch: StatusSwitch = StatusSwitch.ON,
    operation: StatusOperation | int = StatusOperation.COOL,
    fan_mode: StatusFanMode = StatusFanMode.LOW,
    target_temperature: int = 26,
    current_temperature: int = 25,
    address: tuple[int, int] = DEVICE_ADDRESS,
) -> AcStatus:
    """Build a status frame as the gateway would push it.

    ``operation`` also takes a raw value, so a test can feed the decoder an
    operation the library does not know.
    """
    return AcStatus(
        address[0],
        address[1],
        switch.value,
        target_temperature,
        operation.value if isinstance(operation, StatusOperation) else operation,
        fan_mode.value,
        current_temperature,
        0,
        0,
        0,
    )


class FakeGateway:
    """Test double for the zhong_hong_hvac gateway.

    The devices on top of it are the real library class, so the tests exercise
    the actual protocol decoding and command building.
    """

    def __init__(self) -> None:
        """Initialize the fake gateway."""
        self.ip_addr = HOST
        self.port = DEFAULT_PORT
        self.gw_addr = DEFAULT_GATEWAY_ADDRESS
        self.connected = True

        self.discovery_result: list[tuple[int, int]] = [DEVICE_ADDRESS]
        self.discovery_error: Exception | None = None
        # The bound each discovery was given, so a test can tell the config
        # flow's bounded call from the config entry's unbounded one.
        self.discovery_timeouts: list[float | None] = []

        self.send_result = True
        self.send_results: list[bool] = []
        self.query_all_status_result = True
        # The wire names of the speeds the units behind this gateway have.
        self.supported_fan_modes = {mode.name for mode in StatusFanMode}

        self.send_calls = 0
        self.query_all_status_calls = 0
        self.start_listen_calls = 0
        self.stop_listen_calls = 0

        self._devices: dict[tuple[int, int], object] = {}
        self._status_callbacks: dict[tuple[int, int], Callable[[AcStatus], None]] = {}

    def discovery_ac(self, timeout: float | None = None) -> list[tuple[int, int]]:
        """Return the devices behind the gateway."""
        self.discovery_timeouts.append(timeout)
        if self.discovery_error is not None:
            raise self.discovery_error
        return self.discovery_result

    def add_status_callback(self, ac_addr: AcAddr, func: Callable) -> None:
        """Register the library's own status handler for a device."""
        self._status_callbacks[(ac_addr.addr_out, ac_addr.addr_in)] = func

    def add_device(self, device) -> None:
        """Register a device."""
        self._devices[(device.addr_out, device.addr_in)] = device

    def get_device(self, addr: AcAddr):
        """Return a registered device."""
        return self._devices.get((addr.addr_out, addr.addr_in))

    def start_listen(self) -> bool:
        """Start the listener thread."""
        self.start_listen_calls += 1
        return True

    def stop_listen(self) -> None:
        """Stop the listener thread."""
        self.stop_listen_calls += 1

    def query_all_status(self) -> bool:
        """Ask the gateway to re-send the state of every device."""
        self.query_all_status_calls += 1
        return self.query_all_status_result

    def query_status(self, ac_addr: AcAddr) -> bool:
        """Ask the gateway to re-send the state of one device."""
        return self.send_result

    def send(self, ac_data) -> bool:
        """Send a command to the gateway.

        A fan speed the units have is reflected back the way a real gateway
        does, so that a unit which only has three speeds simply never confirms
        the other two. Only the unit the command is addressed to is touched —
        the payload carries the address, the same as on the wire.

        Results queued in ``send_results`` are returned in order, so a test can
        let one command succeed and the next one fail.
        """
        self.send_calls += 1

        header = ac_data.header
        if header.func_code is FuncCode.CTL_FAN_MODE:
            speed = header.ctl_code
            if speed.name in self.supported_fan_modes:
                for ac_addr in ac_data.payload:
                    device = self._devices.get((ac_addr.addr_out, ac_addr.addr_in))
                    if device is not None:
                        device.set_attr(FuncCode.CTL_FAN_MODE, speed)

        if self.send_results:
            return self.send_results.pop(0)
        return self.send_result

    def push_status(self, status: AcStatus) -> None:
        """Push a status frame the way the listener thread would."""
        self._status_callbacks[(status.addr_out, status.addr_in)](status)


@pytest.fixture
def gateway() -> FakeGateway:
    """Return a fake gateway."""
    return FakeGateway()


@pytest.fixture
def mock_gateway(gateway: FakeGateway) -> Generator[FakeGateway]:
    """Patch the gateway used by both the config flow and the config entry."""
    with (
        patch(
            "homeassistant.components.zhong_hong.ZhongHongGateway",
            return_value=gateway,
        ),
        patch(
            "homeassistant.components.zhong_hong.config_flow.ZhongHongGateway",
            return_value=gateway,
        ),
    ):
        yield gateway


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.zhong_hong.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for the fake gateway."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=HOST,
        data={
            CONF_HOST: HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_GATEWAY_ADDRESS: DEFAULT_GATEWAY_ADDRESS,
        },
    )
