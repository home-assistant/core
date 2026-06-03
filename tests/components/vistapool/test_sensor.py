"""Tests for the Vistapool sensor platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_sensors_default_modules(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test sensors come up with the expected states for the default fixture."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Always-on sensors.
    assert hass.states.get("sensor.my_pool_temperature").state == "25.5"
    assert hass.states.get("sensor.my_pool_filtration_intel_time") is not None

    # Module-gated; the fixture sets hasPH=1, hasRX=1, hasHidro=1 with
    # is_electrolysis=True.
    assert hass.states.get("sensor.my_pool_ph").state == "7.42"
    assert hass.states.get("sensor.my_pool_redox_potential").state == "707"
    assert hass.states.get("sensor.my_pool_electrolysis").state == "5.0"

    # Module-gated and disabled in the fixture (hasCD=0, hasCL=0, hasUV=0).
    assert hass.states.get("sensor.my_pool_conductivity") is None
    assert hass.states.get("sensor.my_pool_chlorine") is None
    assert hass.states.get("sensor.my_pool_uv") is None


async def test_sensors_hydrolysis_branch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the hydrolysis (non-electrolysis) branch creates the right sensor."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasHidro": 1, "version": 1},
        "hidro": {"is_electrolysis": False, "current": 50},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.my_pool_hydrolysis") is not None
    assert hass.states.get("sensor.my_pool_electrolysis") is None


async def test_sensors_all_modules_enabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test every module-gated sensor comes up when all `has*` flags are set."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {
            "hasCD": 1,
            "hasCL": 1,
            "hasPH": 1,
            "hasRX": 1,
            "hasUV": 1,
            "hasHidro": 1,
            "version": 1,
        },
        "hidro": {"is_electrolysis": True, "current": 50},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for name in (
        "conductivity",
        "chlorine",
        "ph",
        "redox_potential",
        "uv",
        "electrolysis",
    ):
        assert hass.states.get(f"sensor.my_pool_{name}") is not None


async def test_sensors_multi_pool(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test setup creates sensors for every pool on the account."""
    mock_vistapool_client.get_pools.return_value = {
        "pool_a": "Pool A",
        "pool_b": "Pool B",
    }
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.pool_a_temperature").state == "25.5"
    assert hass.states.get("sensor.pool_b_temperature").state == "25.5"
