"""Tests for Specialized Turbo sensor entities."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from specialized_turbo import AssistLevel, TelemetrySnapshot
from specialized_turbo.session import TCU1Session

from homeassistant.components.specialized_turbo.sensor import (
    PARALLEL_UPDATES,
    SENSOR_DESCRIPTIONS,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import TCX_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

BATTERY_ENTITY_ID = "sensor.mock_title"
SPEED_ENTITY_ID = "sensor.mock_title_2"
ASSIST_LEVEL_ENTITY_ID = "sensor.mock_title_assist_level"


@pytest.fixture
def mock_ble_coordinator() -> Generator[MagicMock]:
    """Mock BLE coordinator connection dependencies for sensor tests."""
    mock_client = MagicMock(is_connected=True)
    mock_client.start_notify = AsyncMock()
    mock_client.stop_notify = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.pair = AsyncMock()

    with (
        patch(
            "homeassistant.components.specialized_turbo.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.specialized_turbo.coordinator.identify_tcx",
            new_callable=AsyncMock,
            return_value=TCU1Session(),
        ),
    ):
        yield mock_client


async def _setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the integration (call inside mock_ble_coordinator fixture scope)."""
    mock_config_entry.add_to_hass(hass)
    inject_bluetooth_service_info(hass, TCX_SERVICE_INFO)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


# --- Sensor description metadata ---


def test_sensor_descriptions_count() -> None:
    """Test that all 26 sensor descriptions are defined."""
    assert len(SENSOR_DESCRIPTIONS) == 26


def test_parallel_updates_zero() -> None:
    """Test PARALLEL_UPDATES is 0 for push-based coordinator."""
    assert PARALLEL_UPDATES == 0


def test_all_descriptions_have_translation_key_or_device_class() -> None:
    """Test that all descriptions have a translation key or device class for naming."""
    for desc in SENSOR_DESCRIPTIONS:
        assert desc.translation_key is not None or desc.device_class is not None, (
            f"{desc.key} has neither translation_key nor device_class"
        )


def test_value_fn_returns_none_for_empty_snapshot() -> None:
    """Test that all value functions handle empty snapshot gracefully."""
    snap = TelemetrySnapshot()
    for desc in SENSOR_DESCRIPTIONS:
        value = desc.value_fn(snap)
        assert value is None, f"{desc.key} returned {value} for empty snapshot"


# --- Entity state tests ---


@pytest.mark.usefixtures("mock_ble_coordinator")
async def test_sensors_unavailable_before_first_message(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that sensors are unavailable before any BLE message is received."""
    await _setup_integration(hass, mock_config_entry)

    state = hass.states.get(BATTERY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_ble_coordinator")
async def test_battery_sensor_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test battery charge percent sensor reflects snapshot value."""
    await _setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    coordinator.snapshot.battery.charge_pct = 85
    coordinator.snapshot.message_count = 1
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(BATTERY_ENTITY_ID)
    assert state is not None
    assert state.state == "85"


@pytest.mark.usefixtures("mock_ble_coordinator")
async def test_speed_sensor_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test speed sensor reflects snapshot value."""
    await _setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    coordinator.snapshot.motor.speed_kmh = 25.5
    coordinator.snapshot.message_count = 1
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(SPEED_ENTITY_ID)
    assert state is not None
    assert state.state == "25.5"


@pytest.mark.parametrize(
    ("assist_level", "expected_state"),
    [
        (AssistLevel.OFF, "off"),
        (AssistLevel.ECO, "eco"),
        (AssistLevel.TRAIL, "trail"),
        (AssistLevel.TURBO, "turbo"),
    ],
)
@pytest.mark.usefixtures("mock_ble_coordinator")
async def test_assist_level_sensor_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    assist_level: AssistLevel,
    expected_state: str,
) -> None:
    """Test assist level sensor maps enum values to lowercase strings."""
    await _setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    coordinator.snapshot.motor.assist_level = assist_level
    coordinator.snapshot.message_count = 1
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(ASSIST_LEVEL_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("mock_ble_coordinator")
async def test_assist_level_unknown_int(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test assist level sensor returns unknown for unrecognized int values."""
    await _setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    coordinator.snapshot.motor.assist_level = 99
    coordinator.snapshot.message_count = 1
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(ASSIST_LEVEL_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
