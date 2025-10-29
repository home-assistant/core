"""Test Curve sensors."""

from typing import Any

import pytest

from homeassistant.components.curve.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import MOCK_STEP_SEGMENTS

from tests.common import MockConfigEntry


async def test_sensor_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test sensor setup."""
    mock_config_entry.add_to_hass(hass)

    hass.states.async_set("sensor.test_source", "5")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Created and correctly computed?
    assert hass.states.get("sensor.test_curve").state == "2.5"


async def test_sensor_linear_interpolation(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test linear interpolation."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Test various points on the curve
    test_points = [
        (0, "0.0"),  # Start of first segment
        (5, "2.5"),  # Middle of first segment
        (10, "5.0"),  # End of first segment / start of second
        (15, "10.0"),  # Middle of second segment
        (20, "15.0"),  # End of second segment
    ]

    for x, expected_y in test_points:
        hass.states.async_set("sensor.test_source", str(x))
        await hass.async_block_till_done()
        assert hass.states.get("sensor.test_curve").state == expected_y, (
            f"Failed at x={x}"
        )


async def test_sensor_step_interpolation(hass: HomeAssistant) -> None:
    """Test step interpolation."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Step Curve",
        options={
            "name": "Test Step Curve",
            "source": "sensor.test_source",
            "segments": MOCK_STEP_SEGMENTS,
        },
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Test step interpolation - should use y0 for entire segment
    test_points = [
        (0, "0.0"),
        (5, "0.0"),  # Still using y0 of first segment
        (9.99, "0.0"),  # Still using y0 of first segment
        (10, "0.0"),  # At boundary, matches first segment
        (10.01, "5.0"),  # Now in second segment, using its y0
        (15, "5.0"),
        (20, "5.0"),
    ]

    for x, expected_y in test_points:
        hass.states.async_set("sensor.test_source", str(x))
        await hass.async_block_till_done()
        assert hass.states.get("sensor.test_step_curve").state == expected_y, (
            f"Failed at x={x}"
        )


async def test_sensor_out_of_bounds(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test values outside the curve range."""
    mock_config_entry.add_to_hass(hass)

    hass.states.async_set("sensor.test_source", "0")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Test below minimum
    hass.states.async_set("sensor.test_source", "-10")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test_curve").state == "0.0"  # Clamped to first y0

    # Test above maximum
    hass.states.async_set("sensor.test_source", "100")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test_curve").state == "15.0"  # Clamped to last y1


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(STATE_UNAVAILABLE, id="state_unavailable"),
        pytest.param(STATE_UNKNOWN, id="state_unknown"),
        pytest.param("not_a_number", id="invalid_value"),
    ],
)
async def test_sensor_bad_source(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, source: Any
) -> None:
    """Test handling of unavailable source sensor."""
    mock_config_entry.add_to_hass(hass)

    hass.states.async_set("sensor.test_source", source)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test_curve").state == STATE_UNAVAILABLE


async def test_sensor_state_change(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test sensor updates when source changes."""
    mock_config_entry.add_to_hass(hass)

    hass.states.async_set("sensor.test_source", "5")
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test_curve").state == "2.5"

    hass.states.async_set("sensor.test_source", "15")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test_curve").state == "10.0"


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    hass.states.async_set("sensor.test_source", "5")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test_curve").state == "2.5"

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test_curve").state == STATE_UNAVAILABLE
