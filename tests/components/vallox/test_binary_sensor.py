"""Tests for Vallox binary sensor platform."""
from typing import Any

import pytest

from homeassistant.core import HomeAssistant

from .conftest import patch_metrics

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("metrics", "expected_state"),
    [
        ({"A_CYC_IO_HEATER": 1}, "on"),
        ({"A_CYC_IO_HEATER": 0}, "off"),
    ],
)
async def test_binary_sensor_entitity(
    metrics: dict[str, Any],
    expected_state: str,
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
):
    """Test binary sensor with metrics."""
    # Act
    with patch_metrics(metrics=metrics):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("binary_sensor.vallox_post_heater")
    assert sensor.state == expected_state
