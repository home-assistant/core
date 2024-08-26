"""Tradfri fan (recognised as air purifiers in the IKEA ecosystem) platform tests."""

from __future__ import annotations

from typing import Any

import pytest
from pytradfri.const import (
    ATTR_AIR_PURIFIER_FAN_SPEED,
    ATTR_AIR_PURIFIER_MODE,
    ATTR_REACHABLE_STATE,
    ROOT_AIR_PURIFIER,
)
from pytradfri.device import Device

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from .common import CommandStore, setup_integration


@pytest.mark.parametrize("device", ["air_purifier"], indirect=True)
async def test_fan_available(
    hass: HomeAssistant,
    command_store: CommandStore,
    device: Device,
) -> None:
    """Test fan available property."""
    entity_id = "fan.test"
    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_PERCENTAGE] == 18
    assert state.attributes[ATTR_PERCENTAGE_STEP] == pytest.approx(2.040816)
    assert state.attributes[ATTR_PRESET_MODES] == ["Auto"]
    assert state.attributes[ATTR_PRESET_MODE] is None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 57

    await command_store.trigger_observe_callback(
        hass, device, {ATTR_REACHABLE_STATE: 0}
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device", ["air_purifier"], indirect=True)
@pytest.mark.parametrize(
    (
        "service",
        "service_data",
        "device_state",
        "expected_state",
        "expected_percentage",
        "expected_preset_mode",
    ),
    [
        (
            SERVICE_SET_PERCENTAGE,
            {ATTR_PERCENTAGE: 50},
            {
                ATTR_AIR_PURIFIER_FAN_SPEED: 25,
                ATTR_AIR_PURIFIER_MODE: 25,
            },
            STATE_ON,
            49,
            None,
        ),
        (
            SERVICE_SET_PERCENTAGE,
            {ATTR_PERCENTAGE: 0},
            {
                ATTR_AIR_PURIFIER_FAN_SPEED: 0,
                ATTR_AIR_PURIFIER_MODE: 0,
            },
            STATE_OFF,
            None,
            None,
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_PERCENTAGE: 50},
            {
                ATTR_AIR_PURIFIER_FAN_SPEED: 25,
                ATTR_AIR_PURIFIER_MODE: 25,
            },
            STATE_ON,
            49,
            None,
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_PRESET_MODE: "Auto"},
            {
                ATTR_AIR_PURIFIER_MODE: 1,
            },
            STATE_ON,
            18,
            "Auto",
        ),
        (
            SERVICE_TURN_ON,
            {},
            {
                ATTR_AIR_PURIFIER_MODE: 1,
            },
            STATE_ON,
            18,
            "Auto",
        ),
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "Auto"},
            {
                ATTR_AIR_PURIFIER_MODE: 1,
            },
            STATE_ON,
            18,
            "Auto",
        ),
        (
            SERVICE_TURN_OFF,
            {},
            {
                ATTR_AIR_PURIFIER_FAN_SPEED: 0,
                ATTR_AIR_PURIFIER_MODE: 0,
            },
            STATE_OFF,
            None,
            None,
        ),
    ],
)
async def test_services(
    hass: HomeAssistant,
    command_store: CommandStore,
    device: Device,
    service: str,
    service_data: dict[str, Any],
    device_state: dict[str, Any],
    expected_state: str,
    expected_percentage: int | None,
    expected_preset_mode: str | None,
) -> None:
    """Test fan services."""
    entity_id = "fan.test"
    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_PERCENTAGE] == 18
    assert state.attributes[ATTR_PERCENTAGE_STEP] == pytest.approx(2.040816)
    assert state.attributes[ATTR_PRESET_MODES] == ["Auto"]
    assert state.attributes[ATTR_PRESET_MODE] is None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 57

    await hass.services.async_call(
        FAN_DOMAIN,
        service,
        {"entity_id": entity_id, **service_data},
        blocking=True,
    )
    await hass.async_block_till_done()

    await command_store.trigger_observe_callback(
        hass,
        device,
        {ROOT_AIR_PURIFIER: [device_state]},
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected_state
    assert state.attributes[ATTR_PERCENTAGE] == expected_percentage
    assert state.attributes[ATTR_PRESET_MODE] == expected_preset_mode
