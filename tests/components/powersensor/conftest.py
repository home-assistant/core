"""Common test fixtures for powersensor Home Assistant integration tests."""

from unittest.mock import AsyncMock, patch

from powersensor_local import PlugListenerUdp, VirtualHousehold
import pytest

from homeassistant.components.powersensor.config_flow import PowersensorConfigFlow
from homeassistant.components.powersensor.const import DOMAIN, ROLE_UNKNOWN
from homeassistant.components.powersensor.models import PowersensorRuntimeData
from homeassistant.config_entries import ConfigEntryState

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Placeholder fixture that is a no-op for enabling custom integrations."""


@pytest.fixture(autouse=True)
def no_powersensor_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch for UDP listener making 'connect' a no-op safe for testing."""

    def no_connect(self):
        pass

    monkeypatch.setattr(PlugListenerUdp, "connect", no_connect)


@pytest.fixture(autouse=True)
def no_zeroconf() -> None:
    """Prevent the zeroconf component from setting up (it opens real sockets).

    Patches async_setup so the dependency loader considers zeroconf ready
    without ever touching the network. Also stubs out the two entry-points
    our integration calls at runtime so individual tests that need finer
    control can override them via their own monkeypatches.
    """
    with (
        patch(
            "homeassistant.components.zeroconf.async_setup",
            return_value=True,
        ),
        patch(
            "homeassistant.components.zeroconf.async_get_instance",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "zeroconf.ServiceBrowser.__init__",
            return_value=None,
        ),
    ):
        yield


class MockDispatcher:
    """Minimal stand-in for PowersensorMessageDispatcher used in fixtures."""

    def __init__(self) -> None:
        """Initialize per-instance dispatcher state for test isolation."""
        self.sensors: dict[str, str | None] = {
            "c001eat5": "house-net",
            "cafebabe": "solar",
            "d3adB33f": None,
        }
        self.plugs: dict = {}
        self.on_start_sensor_queue: dict = {}


@pytest.fixture
def def_config_entry():
    """A mock config entry for powersensor integration testing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "devices": {
                "0123456789abcd": {
                    "name": "test-plug",
                    "display_name": "Test Plug",
                    "mac": "0123456789abcd",
                    "host": "192.168.0.33",
                    "port": 49476,
                }
            },
            "roles": {
                "c001eat5": "house-net",
                "cafebabe": "solar",
                "d3adB33f": ROLE_UNKNOWN,
            },
        },
        entry_id="test",
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
        state=ConfigEntryState.LOADED,
    )

    mock_dispatcher = MockDispatcher()
    entry.runtime_data = PowersensorRuntimeData(
        vhh=VirtualHousehold(False),
        dispatcher=mock_dispatcher,  # type: ignore[arg-type]
        zeroconf=None,
    )
    return entry
