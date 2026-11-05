"""Tests for Samsung dishwasher delayed-start reporting."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from . import set_attribute_value, setup_integration


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
async def test_dishwasher_delayed_start_sensor_values(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Expose delayed start without guessing from the machine state."""
    set_attribute_value(
        devices,
        Capability.SAMSUNG_CE_DISHWASHER_JOB_STATE,
        Attribute.DISHWASHER_JOB_STATE,
        "delayWashing",
    )
    set_attribute_value(
        devices,
        Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
        Attribute.TIME_LEFT_TO_START,
        634,
    )
    set_attribute_value(
        devices,
        Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
        Attribute.REMAINING_TIME,
        180,
    )

    await setup_integration(hass, mock_config_entry)

    states = {state.entity_id: state for state in hass.states.async_all("sensor")}
    assert any(
        entity_id.endswith("_detailed_job_state") and state.state == "delay_washing"
        for entity_id, state in states.items()
    )
    assert any(
        entity_id.endswith("_time_left_to_start") and state.state == "634"
        for entity_id, state in states.items()
    )
    assert any(
        entity_id.endswith("_remaining_cycle_time") and state.state == "180"
        for entity_id, state in states.items()
    )
