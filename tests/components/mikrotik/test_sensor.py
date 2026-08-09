"""Tests for the Mikrotik sensor platform."""

from unittest.mock import patch

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_mikrotik_entry

from tests.common import snapshot_platform


@freeze_time("2026-01-01T12:00:00+00:00")
async def test_sensor_entities_created(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Mikrotik sensor entities are created with expected values."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SENSOR]):
        config_entry = await setup_mikrotik_entry(hass)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_sensor_wrong_data(hass: HomeAssistant) -> None:
    """Test Mikrotik sensor entities handle missing data gracefully."""
    await setup_mikrotik_entry(
        hass,
        health_data=[
            {"name": "voltage", "value": 24.2},
        ],
        system_data=[
            {
                "cpu-load": 15,
                "total-memory": 0,
                "free-memory": 200,
                "total-hdd-space": 0,
                "free-hdd-space": 25,
                "uptime": None,
            }
        ],
    )

    assert (state := hass.states.get("sensor.mikrotik_voltage"))
    assert state.state == "24.2"

    assert (state := hass.states.get("sensor.mikrotik_temperature")) is None

    assert (state := hass.states.get("sensor.mikrotik_cpu_usage"))
    assert state.state == "15"

    assert (state := hass.states.get("sensor.mikrotik_memory_usage"))
    assert state.state == STATE_UNKNOWN

    assert (state := hass.states.get("sensor.mikrotik_disk_usage"))
    assert state.state == STATE_UNKNOWN

    assert (state := hass.states.get("sensor.mikrotik_uptime")) is None


async def test_sensor_named_health_metrics(hass: HomeAssistant) -> None:
    """Test health sensors match by name, not list position.

    Newer RouterOS boards expose cpu-temperature and status strings like
    fan-state=ok at positions that older boards used for temperature/voltage.
    """
    await setup_mikrotik_entry(
        hass,
        health_data=[
            {"name": "cpu-temperature", "value": 57, "type": "C"},
            {"name": "fan-state", "value": "ok", "type": ""},
            {"name": "fan1-speed", "value": 3855, "type": "RPM"},
            {"name": "board-temperature1", "value": 38, "type": "C"},
            {"name": "psu1-state", "value": "ok", "type": ""},
        ],
    )

    assert (state := hass.states.get("sensor.mikrotik_temperature"))
    assert state.state == "57.0"

    assert hass.states.get("sensor.mikrotik_voltage") is None


async def test_sensor_non_numeric_health_value(hass: HomeAssistant) -> None:
    """Test non-numeric health values do not create temperature/voltage sensors."""
    await setup_mikrotik_entry(
        hass,
        health_data=[
            {"name": "temperature", "value": "ok"},
            {"name": "voltage", "value": "ok"},
        ],
    )

    assert hass.states.get("sensor.mikrotik_temperature") is None
    assert hass.states.get("sensor.mikrotik_voltage") is None


@pytest.mark.parametrize(
    "uptime_api",
    [
        pytest.param("3u2h3m4s", id="invalid_unit"),
        pytest.param("2h30", id="missing_unit"),
    ],
)
@freeze_time("2026-01-01T12:00:00+00:00")
async def test_sensor_bad_uptime_data(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    uptime_api: str,
) -> None:
    """Test Mikrotik sensor entities handle missing data gracefully."""

    await setup_mikrotik_entry(
        hass,
        system_data=[
            {
                "cpu-load": 15,
                "total-memory": 0,
                "free-memory": 200,
                "total-hdd-space": 0,
                "free-hdd-space": 25,
                "uptime": uptime_api,
            }
        ],
    )

    assert f"Unknown uptime format: {uptime_api}" in caplog.text

    assert (state := hass.states.get("sensor.mikrotik_uptime"))
    assert state.state == STATE_UNKNOWN


async def test_sensor_no_data(hass: HomeAssistant) -> None:
    """Test Mikrotik sensor entities handle missing data gracefully."""
    await setup_mikrotik_entry(
        hass,
        health_data=[],
        system_data=[],
    )

    assert hass.states.get("sensor.mikrotik_voltage") is None
    assert hass.states.get("sensor.mikrotik_temperature") is None
    assert hass.states.get("sensor.mikrotik_cpu_usage") is None
    assert hass.states.get("sensor.mikrotik_memory_usage") is None
    assert hass.states.get("sensor.mikrotik_disk_usage") is None
    assert hass.states.get("sensor.mikrotik_uptime") is None
