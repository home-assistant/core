"""Tests for the Mikrotik sensor platform."""

from typing import Any
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant.components import mikrotik, sensor
from homeassistant.components.mikrotik.const import HEALTH, SYSTEM
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_DATA

from tests.common import MockConfigEntry

HEALTH_DATA = [
    {"name": "voltage", "value": 24.2},
    {"name": "temperature", "value": 50.0},
]

SYSTEM_DATA = [
    {
        "cpu-load": 15,
        "total-memory": 1000,
        "free-memory": 200,
        "total-hdd-space": 100,
        "free-hdd-space": 25,
        "uptime": "1w2d3h4m5s",
    }
]

EXPECTED_SENSOR_STATES = [
    pytest.param("ABC123_voltage", "24.2", id="voltage"),
    pytest.param("ABC123_temperature", "50.0", id="temperature"),
    pytest.param("ABC123_cpu-load", "15", id="cpu_load"),
    pytest.param("ABC123_memory-usage", "80.0", id="memory_usage"),
    pytest.param("ABC123_disk-usage", "75.0", id="disk_usage"),
    pytest.param(
        "ABC123_uptime",
        "2025-12-23T08:55:55+00:00",
        id="uptime",
    ),
]


async def _setup_entry_with_sensor_data(  # pylint: disable=dangerous-default-value
    hass: HomeAssistant,
    health_data: list[dict[str, Any]] = HEALTH_DATA,
    system_data: list[dict[str, Any]] = SYSTEM_DATA,
) -> MockConfigEntry:
    """Set up Mikrotik integration with health and system sensor data."""

    def mock_command(self, cmd: str, params=None, suppress_errors: bool = False):
        """Return mocked Mikrotik API responses for known service commands."""

        command_responses = {
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IDENTITY]: [
                {"name": "Mikrotik"}
            ],
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.INFO]: [
                {
                    "model": "RB5009",
                    "current-firmware": "7.18.2",
                    "serial-number": "ABC123",
                }
            ],
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_CAPSMAN]: [],
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_WIRELESS]: [],
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_WIFIWAVE2]: [],
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_WIFI]: [],
            mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.DHCP]: [],
            mikrotik.const.MIKROTIK_SERVICES[HEALTH]: health_data,
            mikrotik.const.MIKROTIK_SERVICES[SYSTEM]: system_data,
        }
        return command_responses.get(cmd, [])

    config_entry = MockConfigEntry(domain=mikrotik.DOMAIN, data=MOCK_DATA)
    config_entry.add_to_hass(hass)

    with (
        patch("librouteros.connect"),
        patch.object(mikrotik.coordinator.MikrotikData, "command", new=mock_command),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


@freeze_time("2026-01-01T12:00:00+00:00")
@pytest.mark.parametrize(("entity_unique_id", "expected_state"), EXPECTED_SENSOR_STATES)
async def test_sensor_entities_created(
    hass: HomeAssistant,
    entity_unique_id: str,
    expected_state: str,
) -> None:
    """Test Mikrotik sensor entities are created with expected values."""
    await _setup_entry_with_sensor_data(hass)

    entity_registry = er.async_get(hass)

    entity_id = entity_registry.async_get_entity_id(
        sensor.DOMAIN,
        mikrotik.DOMAIN,
        entity_unique_id,
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


async def test_sensor_missing_wrong_data(hass: HomeAssistant) -> None:
    """Test Mikrotik sensor entities handle missing data gracefully."""
    await _setup_entry_with_sensor_data(
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

    assert (state := hass.states.get("sensor.mikrotik_cpu_load")) is None


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

    await _setup_entry_with_sensor_data(
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
