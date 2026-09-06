"""Tests for the Mikrotik sensor platform."""

from typing import Any
from unittest.mock import patch

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
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


@pytest.mark.parametrize(
    ("health_data", "system_data", "existing_states", "missing_entities"),
    [
        pytest.param(
            [{"name": "voltage", "value": 24.2}],
            [
                {
                    "cpu-load": 15,
                    "total-memory": 0,
                    "free-memory": 200,
                    "total-hdd-space": 0,
                    "free-hdd-space": 25,
                    "uptime": None,
                }
            ],
            {
                "sensor.mikrotik_voltage": "24.2",
                "sensor.mikrotik_cpu_usage": "15",
            },
            [
                "sensor.mikrotik_temperature",
                "sensor.mikrotik_memory_usage",
                "sensor.mikrotik_disk_usage",
                "sensor.mikrotik_uptime",
            ],
            id="degenerate_data",
        ),
        pytest.param(
            [],
            [],
            {},
            [
                "sensor.mikrotik_voltage",
                "sensor.mikrotik_temperature",
                "sensor.mikrotik_cpu_usage",
                "sensor.mikrotik_memory_usage",
                "sensor.mikrotik_disk_usage",
                "sensor.mikrotik_uptime",
            ],
            id="no_data",
        ),
    ],
)
async def test_sensor_missing_or_wrong_data(
    hass: HomeAssistant,
    health_data: list[dict[str, Any]],
    system_data: list[dict[str, Any]],
    existing_states: dict[str, str],
    missing_entities: list[str],
) -> None:
    """Test Mikrotik sensor entities handle missing/wrong data gracefully.

    memory-usage/disk-usage can't be computed when the reported totals are
    zero, and uptime can't be computed without a raw uptime string, so those
    sensors are not created at all.
    """
    await setup_mikrotik_entry(hass, health_data=health_data, system_data=system_data)

    for entity_id, expected_state in existing_states.items():
        assert (state := hass.states.get(entity_id))
        assert state.state == expected_state

    for entity_id in missing_entities:
        assert hass.states.get(entity_id) is None


@pytest.mark.parametrize(
    "uptime_api",
    [
        pytest.param("3u2h3m4s", id="invalid_unit"),
        pytest.param("2h30", id="missing_unit"),
    ],
)
async def test_sensor_bad_uptime_data(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    uptime_api: str,
) -> None:
    """Test Mikrotik sensor entities handle missing data gracefully.

    An uptime string that can't be parsed computes to None, so the sensor is
    not created at all, but the parsing failure is still logged.
    """

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

    assert hass.states.get("sensor.mikrotik_uptime") is None


async def test_sensor_health_data_reordered(hass: HomeAssistant) -> None:
    """Test voltage/temperature are matched by name, not list position.

    Some devices (e.g. netPower 16P) report additional health items such as
    PoE power consumption ahead of voltage, so the sensors must not assume a
    fixed ordering. https://github.com/home-assistant/core/issues/178392
    """
    await setup_mikrotik_entry(
        hass,
        health_data=[
            {"name": "power-consumption", "value": 8.0},
            {"name": "temperature", "value": 50.0},
            {"name": "voltage", "value": 52.0},
        ],
    )

    assert (state := hass.states.get("sensor.mikrotik_voltage"))
    assert state.state == "52.0"

    assert (state := hass.states.get("sensor.mikrotik_temperature"))
    assert state.state == "50.0"
