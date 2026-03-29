"""Common fixtures for Aprilaire tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyaprilaire.const import Attribute
import pytest

from homeassistant.components.aprilaire import PLATFORMS
from homeassistant.components.aprilaire.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_MAC = "aa:bb:cc:dd:ee:ff"
MOCK_HOST = "192.168.1.100"
MOCK_PORT = 7000


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_MAC,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
        },
        title="AprilAire",
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return PLATFORMS


@pytest.fixture(autouse=True)
async def mock_patch_platforms(platforms: list[Platform]) -> AsyncGenerator[None]:
    """Fixture to set up platforms for tests."""
    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
        yield


@pytest.fixture
def base_coordinator_data() -> dict:
    """Return base coordinator data with connection and device info."""
    return {
        Attribute.CONNECTED: True,
        Attribute.STOPPED: False,
        Attribute.RECONNECTING: False,
        Attribute.MAC_ADDRESS: MOCK_MAC,
        Attribute.NAME: "Test Thermostat",
        Attribute.MODEL_NUMBER: 2,
        Attribute.HARDWARE_REVISION: ord("B"),
        Attribute.FIRMWARE_MAJOR_REVISION: 4,
        Attribute.FIRMWARE_MINOR_REVISION: 5,
        Attribute.MODE: 5,
        Attribute.THERMOSTAT_MODES: 5,
        Attribute.HOLD: 0,
        Attribute.FAN_MODE: 2,
        Attribute.AWAY_AVAILABLE: 1,
        Attribute.COOL_SETPOINT: 25.0,
        Attribute.HEAT_SETPOINT: 20.0,
        Attribute.INDOOR_TEMPERATURE_CONTROLLING_SENSOR_STATUS: 0,
        Attribute.INDOOR_TEMPERATURE_CONTROLLING_SENSOR_VALUE: 22.5,
        Attribute.INDOOR_HUMIDITY_CONTROLLING_SENSOR_STATUS: 0,
        Attribute.INDOOR_HUMIDITY_CONTROLLING_SENSOR_VALUE: 45,
        Attribute.OUTDOOR_TEMPERATURE_CONTROLLING_SENSOR_STATUS: 0,
        Attribute.OUTDOOR_TEMPERATURE_CONTROLLING_SENSOR_VALUE: 15.0,
        Attribute.OUTDOOR_HUMIDITY_CONTROLLING_SENSOR_STATUS: 0,
        Attribute.OUTDOOR_HUMIDITY_CONTROLLING_SENSOR_VALUE: 60,
        Attribute.HUMIDIFICATION_AVAILABLE: 2,
        Attribute.HUMIDIFICATION_SETPOINT: 35,
        Attribute.HUMIDIFICATION_STATUS: 2,
        Attribute.DEHUMIDIFICATION_AVAILABLE: 1,
        Attribute.DEHUMIDIFICATION_SETPOINT: 55,
        Attribute.DEHUMIDIFICATION_STATUS: 2,
        Attribute.HEATING_EQUIPMENT_STATUS: 0,
        Attribute.COOLING_EQUIPMENT_STATUS: 0,
        Attribute.AIR_CLEANING_AVAILABLE: 1,
        Attribute.AIR_CLEANING_EVENT: 0,
        Attribute.AIR_CLEANING_MODE: 1,
        Attribute.AIR_CLEANING_STATUS: 2,
        Attribute.VENTILATION_AVAILABLE: 1,
        Attribute.FRESH_AIR_EVENT: 0,
        Attribute.FRESH_AIR_MODE: 1,
        Attribute.VENTILATION_STATUS: 2,
        Attribute.FAN_STATUS: 1,
    }


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock AprilaireClient."""
    client = MagicMock()
    client.start_listen = AsyncMock()
    client.stop_listen = MagicMock()
    client.read_mac_address = AsyncMock()
    client.read_sensors = AsyncMock()
    client.read_control = AsyncMock()
    client.read_scheduling = AsyncMock()
    client.read_thermostat_status = AsyncMock()
    client.read_thermostat_iaq_available = AsyncMock()
    client.read_iaq_status = AsyncMock()
    client.wait_for_response = AsyncMock()
    client.update_mode = AsyncMock()
    client.update_fan_mode = AsyncMock()
    client.update_setpoint = AsyncMock()
    client.set_hold = AsyncMock()
    client.set_humidification_setpoint = AsyncMock()
    client.set_dehumidification_setpoint = AsyncMock()
    client.set_air_cleaning = AsyncMock()
    client.set_fresh_air = AsyncMock()
    client.data = {}
    return client


@pytest.fixture
def mock_aprilaire(
    mock_client: MagicMock,
    base_coordinator_data: dict,
) -> Generator[MagicMock]:
    """Patch AprilaireClient and wire up the data callback."""
    data_callback = None

    def capture_client(host, port, callback, *args, **kwargs):
        nonlocal data_callback
        data_callback = callback

        async def on_start_listen():
            if data_callback:
                data_callback(base_coordinator_data)

        mock_client.start_listen.side_effect = on_start_listen
        mock_client.wait_for_response.return_value = base_coordinator_data
        return mock_client

    with patch(
        "homeassistant.components.aprilaire.coordinator.pyaprilaire.client.AprilaireClient",
        side_effect=capture_client,
    ) as mock_constructor:
        yield mock_constructor


async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the Aprilaire integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
