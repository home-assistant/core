"""Common test fixtures for powersensor Home Assistant integration tests."""

from powersensor_local import PlugListenerUdp
import pytest
import zeroconf

from homeassistant.components.powersensor.config_flow import PowersensorConfigFlow
from homeassistant.components.powersensor.const import DOMAIN
import homeassistant.components.zeroconf
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

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
def no_zeroconf(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch for turning off zeroconf."""

    async def no_zc(hass: HomeAssistant | None):
        return None

    monkeypatch.setattr(homeassistant.components.zeroconf, "async_get_instance", no_zc)

    def empty_zc_init(self, service_type, listener, _):
        pass

    monkeypatch.setattr(zeroconf.ServiceBrowser, "__init__", empty_zc_init)


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
            "with_solar": False,
            "roles": {
                "c001eat5": "house-net",
                "cafebabe": "solar",
                "d3adB33f": "<unknown>",
            },
        },
        entry_id="test",
        version=PowersensorConfigFlow.VERSION,
        minor_version=1,
        state=ConfigEntryState.LOADED,
    )

    class MockDispatcher:
        sensors = ["coo1eat5", "cafebabe", "d3adB33f"]

    entry.runtime_data = {"dispatcher": MockDispatcher()}
    return entry
