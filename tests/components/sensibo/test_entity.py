"""The test for the sensibo entity."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
)
from homeassistant.components.sensibo.const import SENSIBO_ERRORS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    load_int: ConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Sensibo device."""

    state1 = hass.states.get("climate.hallway")
    assert state1

    assert (
        dr.async_entries_for_config_entry(device_registry, load_int.entry_id)
        == snapshot
    )


@pytest.mark.parametrize("p_error", SENSIBO_ERRORS)
async def test_entity_failed_service_calls(
    hass: HomeAssistant,
    p_error: Exception,
    load_int: ConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the Sensibo send command with error."""

    state = hass.states.get("climate.hallway")
    assert state

    mock_client.async_set_ac_state_property.return_value = {
        "result": {"status": "Success"}
    }

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_FAN_MODE: "low"},
        blocking=True,
    )

    state = hass.states.get("climate.hallway")
    assert state.attributes["fan_mode"] == "low"

    mock_client.async_set_ac_state_property.side_effect = p_error

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_FAN_MODE: "low"},
            blocking=True,
        )

    state = hass.states.get("climate.hallway")
    assert state.attributes["fan_mode"] == "low"
