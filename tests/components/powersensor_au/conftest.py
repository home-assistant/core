"""Common test fixtures for powersensor_au Home Assistant integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from powersensor_local import PlugListenerUdp, VirtualHousehold
from powersensor_local.devices import PowersensorDevices
import pytest

from homeassistant.components.powersensor_au.config_flow import PowersensorConfigFlow
from homeassistant.components.powersensor_au.const import DOMAIN, ROLE_UNKNOWN
from homeassistant.components.powersensor_au.models import PowersensorRuntimeData

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def no_zeroconf() -> Generator[None]:
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


@pytest.fixture(autouse=True)
def no_powersensor_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch for UDP listener making 'connect' a no-op safe for testing."""

    def no_connect(self):
        pass

    monkeypatch.setattr(PlugListenerUdp, "connect", no_connect)


def _make_mock_devices() -> MagicMock:
    """Return a minimal mock for PowersensorDevices.

    Provides the subscribe/unsubscribe/stop interface that the dispatcher
    and teardown code call. start() and rescan() are AsyncMocks so tests
    can await them or assert call counts without touching the network.
    """
    devices = MagicMock(spec=PowersensorDevices)
    devices.start = AsyncMock(return_value=0)
    devices.rescan = AsyncMock()
    devices.stop = AsyncMock()
    # subscribe/unsubscribe are synchronous in the real class.
    devices.subscribe = MagicMock()
    devices.unsubscribe = MagicMock()
    return devices


class MockDispatcher:
    """Minimal stand-in for PowersensorMessageDispatcher used in fixtures."""

    def __init__(self) -> None:
        """Initialise per-instance dispatcher state for test isolation."""
        self.sensors: dict[str, str | None] = {
            "c001eat5": "house-net",
            "cafebabe": "solar",
            "d3adB33f": None,
        }
        self.plugs: set[str] = set()

    async def disconnect(self) -> None:
        """No-op teardown."""


@pytest.fixture
def def_config_entry():
    """A mock config entry for powersensor_au integration testing.

    Uses the refactored PowersensorRuntimeData shape: vhh, dispatcher, devices.
    The entry is created in NOT_LOADED state so that tests using
    hass.config_entries.async_setup() can set it up through the normal
    HA config entry machinery without hitting OperationNotAllowed.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "roles": {
                "c001eat5": "house-net",
                "cafebabe": "solar",
                "d3adB33f": ROLE_UNKNOWN,
            },
        },
        entry_id="test",
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
    )

    entry.runtime_data = PowersensorRuntimeData(
        vhh=VirtualHousehold(False),
        dispatcher=MockDispatcher(),
        devices=_make_mock_devices(),
    )
    return entry
