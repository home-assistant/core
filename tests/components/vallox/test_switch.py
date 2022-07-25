"""Tests for Vallox switch platform."""
import pytest

from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

from .conftest import patch_metrics, patch_metrics_set

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "entity_id,metric_key, value",
    [
        ("switch.vallox_bypass_locked", "A_CYC_BYPASS_LOCKED", 1),
        ("switch.vallox_bypass_locked", "A_CYC_BYPASS_LOCKED", 0),
    ],
)
async def test_switch_entities(
    entity_id, metric_key, value, mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test switch entities."""
    # Arrange
    metrics = {metric_key: value}

    # Act
    with patch_metrics(metrics=metrics):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get(entity_id)
    assert sensor.state == "on" if value else "off"


async def test_bypass_lock_switch_entitity_set(
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
):
    """Test bypass lock switch set."""
    # Act
    with patch_metrics(metrics={}), patch_metrics_set() as metrics_set:
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            service_data={ATTR_ENTITY_ID: "switch.vallox_bypass_locked"},
        )
        await hass.async_block_till_done()
        metrics_set.assert_called_once_with({"A_CYC_BYPASS_LOCKED": 1})
