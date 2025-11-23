"""Fixtures for Duosida EV integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

if TYPE_CHECKING:
    from homeassistant.loader import Integration

from custom_components.duosida_ev.const import (
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"


# Mock data - realistic charger status
MOCK_CHARGER_STATUS = {
    "conn_status": 2,  # Charging
    "cp_voltage": 6.0,  # 6V = charging
    "voltage": 230.0,  # L1 voltage
    "voltage_l2": 230.0,
    "voltage_l3": 230.0,
    "current": 16.0,  # 16A charging current
    "current_l2": 16.0,
    "current_l3": 16.0,
    "power": 11040,  # 3 * 230V * 16A
    "temperature_station": 35.0,  # 35°C - charger station temperature
    "session_energy": 5.5,  # 5.5 kWh this session
    "session_time": 120,  # 120 minutes = 2 hours
    "model": "SmartChargePI",
    "manufacturer": "Duosida",
    "firmware": "1.0.0",
}

# Mock configuration entry data
MOCK_CONFIG_ENTRY_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_DEVICE_ID: "03123456789012345678",
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}

# Mock discovered charger
MOCK_DISCOVERED_CHARGER = {
    "ip": "192.168.1.100",
    "port": 9988,
    "device_id": "03123456789012345678",
    "model": "SmartChargePI",
}


class MockDuosidaCharger:
    """Mock DuosidaCharger for testing."""

    def __init__(
        self, host: str, port: int = 9988, device_id: str = "", debug: bool = False
    ):
        """Initialize mock charger."""
        self.host = host
        self.port = port
        self.device_id = device_id
        self.debug = debug
        self._connected = False
        self._status = MOCK_CHARGER_STATUS.copy()

    def connect(self) -> bool:
        """Mock connect."""
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Mock disconnect."""
        self._connected = False

    def get_status(self):
        """Mock get_status - returns self (charger object)."""
        if not self._connected:
            raise ConnectionError("Not connected")
        return self  # Return self so to_dict() can be called on the result

    def to_dict(self) -> dict[str, Any]:
        """Mock to_dict."""
        if not self._connected:
            raise ConnectionError("Not connected")
        return self._status

    def start_charging(self) -> bool:
        """Mock start_charging."""
        if not self._connected:
            return False
        self._status["conn_status"] = 2  # Charging
        return True

    def stop_charging(self) -> bool:
        """Mock stop_charging."""
        if not self._connected:
            return False
        self._status["conn_status"] = 0  # Available
        return True

    def set_max_current(self, current: int) -> bool:
        """Mock set_max_current."""
        if not self._connected:
            return False
        if not 6 <= current <= 32:
            return False
        self._status["current"] = float(current)
        return True

    def set_led_brightness(self, brightness: int) -> bool:
        """Mock set_led_brightness."""
        if not self._connected:
            return False
        if brightness not in (0, 1, 3):
            return False
        return True

    def set_direct_work_mode(self, enabled: bool) -> bool:
        """Mock set_direct_work_mode."""
        if not self._connected:
            return False
        return True

    def set_stop_on_disconnect(self, enabled: bool) -> bool:
        """Mock set_stop_on_disconnect."""
        if not self._connected:
            return False
        return True

    def set_max_voltage(self, voltage: int) -> bool:
        """Mock set_max_voltage."""
        if not self._connected:
            return False
        if not 265 <= voltage <= 290:
            return False
        return True

    def set_min_voltage(self, voltage: int) -> bool:
        """Mock set_min_voltage."""
        if not self._connected:
            return False
        if not 70 <= voltage <= 110:
            return False
        return True


@pytest.fixture
def mock_charger() -> MockDuosidaCharger:
    """Return a mock charger instance."""
    return MockDuosidaCharger(
        host="192.168.1.100",
        port=9988,
        device_id="03123456789012345678",
    )


@pytest.fixture
def mock_duosida_charger() -> Generator[MagicMock, None, None]:
    """Mock the DuosidaCharger class."""
    with (
        patch(
            "custom_components.duosida_ev.DuosidaCharger",
            return_value=MockDuosidaCharger(
                host="192.168.1.100",
                port=9988,
                device_id="03123456789012345678",
            ),
        ) as mock,
        patch(
            "custom_components.duosida_ev.coordinator.DuosidaCharger",
            return_value=MockDuosidaCharger(
                host="192.168.1.100",
                port=9988,
                device_id="03123456789012345678",
            ),
        ),
        patch(
            "custom_components.duosida_ev.config_flow.DuosidaCharger",
            return_value=MockDuosidaCharger(
                host="192.168.1.100",
                port=9988,
                device_id="03123456789012345678",
            ),
        ),
    ):
        yield mock


@pytest.fixture
def mock_discover_chargers() -> Generator[MagicMock, None, None]:
    """Mock discover_chargers function."""
    with patch(
        "custom_components.duosida_ev.config_flow.discover_chargers",
        return_value=[MOCK_DISCOVERED_CHARGER],
    ) as mock:
        yield mock


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Duosida EV Charger",
        data=MOCK_CONFIG_ENTRY_DATA,
        source="user",
        entry_id="test_entry_id",
        unique_id="03123456789012345678",
    )


@pytest.fixture
def mock_integration(hass: HomeAssistant) -> Generator[Integration, None, None]:
    """Mock the integration manifest for tests that need it without full setup."""
    from pathlib import Path

    from homeassistant import loader
    from homeassistant.loader import Integration

    integration_dir = Path(__file__).parent.parent / "custom_components" / "duosida_ev"
    mock_int = Integration(
        hass,
        "custom_components.duosida_ev",
        integration_dir,
        {
            "domain": "duosida_ev",
            "name": "Duosida EV Charger",
            "version": "1.0.0",
            "documentation": "https://github.com/americodias/duosida-ha",
            "issue_tracker": "https://github.com/americodias/duosida-ha/issues",
            "requirements": ["duosida-ev==0.1.3"],
            "codeowners": ["@americodias"],
            "iot_class": "local_polling",
            "integration_type": "device",
        },
    )

    real_async_get_integration = loader.async_get_integration

    async def mock_get_integration(hass_instance, domain):
        if domain == "duosida_ev":
            return mock_int
        return await real_async_get_integration(hass_instance, domain)

    with (
        patch(
            "homeassistant.loader.async_get_integration",
            side_effect=mock_get_integration,
        ),
        patch(
            "homeassistant.requirements.async_get_integration",
            side_effect=mock_get_integration,
        ),
    ):
        yield mock_int


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duosida_charger: MagicMock,
    request: pytest.FixtureRequest,
) -> MockConfigEntry:
    """Set up the integration with mocked charger."""
    from pathlib import Path

    from homeassistant.loader import Integration

    from custom_components.duosida_ev import async_setup_entry

    mock_config_entry.add_to_hass(hass)

    # Create a mock integration manifest
    integration_dir = Path(__file__).parent.parent / "custom_components" / "duosida_ev"
    mock_integration = Integration(
        hass,
        "custom_components.duosida_ev",
        integration_dir,
        {
            "domain": "duosida_ev",
            "name": "Duosida EV Charger",
            "version": "1.0.0",
            "documentation": "https://github.com/americodias/duosida-ha",
            "issue_tracker": "https://github.com/americodias/duosida-ha/issues",
            "requirements": ["duosida-ev==0.1.3"],
            "codeowners": ["@americodias"],
            "iot_class": "local_polling",
            "integration_type": "device",
        },
    )

    # Mock storage to avoid file system access
    # Save reference to real function before patching
    from homeassistant import loader

    real_async_get_integration = loader.async_get_integration

    async def mock_get_integration(hass_instance, domain):
        if domain == "duosida_ev":
            return mock_integration
        # For other domains, call the real function
        return await real_async_get_integration(hass_instance, domain)

    # Apply patches that will persist for the test
    patch_store_load = patch(
        "custom_components.duosida_ev.coordinator.Store.async_load",
        return_value=None,
    )
    patch_store_save = patch(
        "custom_components.duosida_ev.coordinator.Store.async_save",
        return_value=None,
    )
    # Patch async_get_integration at multiple import locations
    patch_get_integration_1 = patch(
        "homeassistant.loader.async_get_integration",
        side_effect=mock_get_integration,
    )
    patch_get_integration_2 = patch(
        "homeassistant.requirements.async_get_integration",
        side_effect=mock_get_integration,
    )

    # Start all patches
    patch_store_load.start()
    patch_store_save.start()
    patch_get_integration_1.start()
    patch_get_integration_2.start()

    # Call setup directly instead of using hass.config_entries.async_setup
    assert await async_setup_entry(hass, mock_config_entry)
    await hass.async_block_till_done()

    # Yield the entry for the test to use
    yield mock_config_entry

    # Cleanup after test
    from custom_components.duosida_ev import async_unload_entry
    from custom_components.duosida_ev.const import COORDINATOR, DOMAIN

    # Explicitly stop the coordinator's refresh timer before unload
    if DOMAIN in hass.data and mock_config_entry.entry_id in hass.data[DOMAIN]:
        if COORDINATOR in hass.data[DOMAIN][mock_config_entry.entry_id]:
            coordinator = hass.data[DOMAIN][mock_config_entry.entry_id][COORDINATOR]
            coordinator._unschedule_refresh()

    # Unload the entry to stop coordinator refresh tasks
    await async_unload_entry(hass, mock_config_entry)
    await hass.async_block_till_done()

    # Stop all patches
    patch_store_load.stop()
    patch_store_save.stop()
    patch_get_integration_1.stop()
    patch_get_integration_2.stop()
