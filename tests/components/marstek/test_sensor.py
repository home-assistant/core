"""Tests for the Marstek sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import MOCK_DEVICE_STATUS

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_setup_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor platform setup."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


async def test_polling_paused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test coordinator respects polling pause."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.is_polling_paused.return_value = True

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()

    mock_udp_client.get_device_status.assert_not_awaited()


async def test_polling_failure_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test polling failures make the sensor unavailable and then recover."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_udp_client.get_device_status.side_effect = [
        OSError("network down"),
        MOCK_DEVICE_STATUS.copy(),
    ]

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.marstek_es5_v1_battery_level").state
        == STATE_UNAVAILABLE
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=22))
    await hass.async_block_till_done()

    assert hass.states.get("sensor.marstek_es5_v1_battery_level").state == "85"


async def test_missing_sensor_fields_do_not_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test missing device status fields are not reported as fallback values."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.get_device_status.side_effect = None
    mock_udp_client.get_device_status.return_value = {
        "battery_power": 1300,
        "pv1_power": 500,
    }

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.marstek_es5_v1_battery_level").state == STATE_UNKNOWN
    assert hass.states.get("sensor.marstek_es5_v1_device_mode").state == STATE_UNKNOWN
    assert (
        hass.states.get("sensor.marstek_es5_v1_battery_status").state == STATE_UNKNOWN
    )
    assert hass.states.get("sensor.marstek_es5_v1_pv1_power").state == "500"
    assert hass.states.get("sensor.marstek_es5_v1_pv1_voltage") is None
    assert hass.states.get("sensor.marstek_es5_v1_pv2_power") is None


async def test_invalid_integer_sensor_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test non-numeric integer sensor values are reported as unknown."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.get_device_status.side_effect = None
    mock_udp_client.get_device_status.return_value = {
        **MOCK_DEVICE_STATUS,
        "battery_power": {},
    }

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.marstek_es5_v1_battery_power").state == STATE_UNKNOWN
