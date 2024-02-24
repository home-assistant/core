"""Tests for Vallox switch platform."""

import pytest

from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

from .conftest import patch_set_values

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("entity_id", "metric_key", "value", "expected_state"),
    [
        ("switch.vallox_bypass_locked", "A_CYC_BYPASS_LOCKED", 1, "on"),
        ("switch.vallox_bypass_locked", "A_CYC_BYPASS_LOCKED", 0, "off"),
    ],
)
async def test_switch_entities(
    entity_id: str,
    metric_key: str,
    value: int,
    expected_state: str,
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
    setup_fetch_metric_data_mock,
) -> None:
    """Test switch entities."""
    # Arrange
    setup_fetch_metric_data_mock(metrics={metric_key: value})

    # Act
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get(entity_id)
    assert sensor
    assert sensor.state == expected_state


@pytest.mark.parametrize(
    ("service", "metric_key", "value"),
    [
        (SERVICE_TURN_ON, "A_CYC_BYPASS_LOCKED", 1),
        (SERVICE_TURN_OFF, "A_CYC_BYPASS_LOCKED", 0),
    ],
)
async def test_bypass_lock_switch_entitity_set(
    service: str,
    metric_key: str,
    value: int,
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test bypass lock switch set."""
    # Act
    with patch_set_values() as set_values:
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            service_data={ATTR_ENTITY_ID: "switch.vallox_bypass_locked"},
        )
        await hass.async_block_till_done()
        set_values.assert_called_once_with({metric_key: value})
