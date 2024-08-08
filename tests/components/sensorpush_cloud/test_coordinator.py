"""Test the SensorPush Cloud coordinator."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.sensorpush_cloud.const import CONF_DEVICE_IDS
from homeassistant.core import HomeAssistant

from .const import MOCK_SAMPLES, MOCK_SENSORS

from tests.common import MockConfigEntry


@pytest.mark.samples(MOCK_SAMPLES)
@pytest.mark.sensors(MOCK_SENSORS)
async def test_update_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test we can update data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert len(coordinator.devices) == len(MOCK_SENSORS)
    assert len(coordinator.data) == len(MOCK_SENSORS)


@pytest.mark.samples(MOCK_SAMPLES)
@pytest.mark.sensors(MOCK_SENSORS)
async def test_update_data_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test we can handle errors when updating data."""
    mock_api.async_sensors.side_effect = Exception("test-message")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert len(coordinator.devices) == 0
    assert len(coordinator.data) == 0


@pytest.mark.samples(MOCK_SAMPLES)
@pytest.mark.sensors(MOCK_SENSORS)
async def test_update_data_inactive(
    hass: HomeAssistant,
    make_config_entry: Callable[[dict[str, Any] | None], MockConfigEntry],
    mock_api: AsyncMock,
) -> None:
    """Test we can ignore inactive devices when updating data."""
    mock_config_entry = make_config_entry(
        {
            CONF_DEVICE_IDS: [
                "test-inactive-1",
                "test-inactive-2",
            ]
        }
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    for device_id in mock_config_entry.data[CONF_DEVICE_IDS]:
        assert device_id not in coordinator.devices
        assert device_id not in coordinator.data
