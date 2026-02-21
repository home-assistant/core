"""Fixtures for the Trane Local integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from steamloop import FanMode, HoldType, ThermostatState, Zone, ZoneMode

from homeassistant.components.trane.const import CONF_SECRET_KEY, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.100"
MOCK_SECRET_KEY = "test_secret_key"
MOCK_ENTRY_ID = "test_entry_id"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        title=f"Thermostat ({MOCK_HOST})",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_SECRET_KEY: MOCK_SECRET_KEY,
        },
    )


def _make_state() -> ThermostatState:
    """Create a mock thermostat state."""
    return ThermostatState(
        zones={
            "1": Zone(
                zone_id="1",
                name="Living Room",
                mode=ZoneMode.AUTO,
                indoor_temperature="72",
                heat_setpoint="68",
                cool_setpoint="76",
                deadband="3",
                hold_type=HoldType.MANUAL,
            ),
        },
        supported_modes=[ZoneMode.OFF, ZoneMode.AUTO, ZoneMode.COOL, ZoneMode.HEAT],
        fan_mode=FanMode.AUTO,
        relative_humidity="45",
    )


@pytest.fixture
def mock_connection() -> Generator[MagicMock]:
    """Return a mocked ThermostatConnection."""
    with (
        patch(
            "homeassistant.components.trane.ThermostatConnection",
            autospec=True,
        ) as mock_cls,
        patch(
            "homeassistant.components.trane.config_flow.ThermostatConnection",
            new=mock_cls,
        ),
    ):
        conn = mock_cls.return_value
        conn.connect = AsyncMock()
        conn.login = AsyncMock()
        conn.pair = AsyncMock()
        conn.disconnect = AsyncMock()
        conn.start_background_tasks = MagicMock()
        conn.set_temperature_setpoint = MagicMock()
        conn.set_zone_mode = MagicMock()
        conn.set_fan_mode = MagicMock()
        conn.set_emergency_heat = MagicMock()
        conn.add_event_callback = MagicMock(return_value=MagicMock())
        conn.state = _make_state()
        conn.secret_key = MOCK_SECRET_KEY
        yield conn


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setup entry."""
    with patch(
        "homeassistant.components.trane.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> MockConfigEntry:
    """Set up the Trane Local integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
