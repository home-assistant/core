"""Test the NUT switch platform."""

import json
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.nut.const import INTEGRATION_SUPPORTED_COMMANDS
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .util import async_init_integration

from tests.common import load_fixture


@pytest.mark.parametrize(
    "model",
    [
        "CP1350C",
        "5E650I",
        "5E850I",
        "CP1500PFCLCD",
        "DL650ELCD",
        "EATON5P1550",
        "blazer_usb",
    ],
)
async def test_switch_ups(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, model: str
) -> None:
    """Tests that there are no standard switches."""

    list_commands_return_value = {
        supported_command: supported_command
        for supported_command in INTEGRATION_SUPPORTED_COMMANDS
    }

    await async_init_integration(
        hass,
        model,
        list_commands_return_value=list_commands_return_value,
    )

    switch = hass.states.get("switch.ups1_power_outlet_1")
    assert not switch


@pytest.mark.parametrize(
    ("model", "unique_id_base"),
    [
        (
            "EATON-EPDU-G3",
            "EATON_ePDU MA 00U-C IN: TYPE 00A 0P OUT: 00xTYPE_A000A00000",
        ),
    ],
)
async def test_switch_pdu_dynamic_outlets(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    model: str,
    unique_id_base: str,
) -> None:
    """Tests that the switch entities are correct."""

    list_commands_return_value = {
        supported_command: supported_command
        for supported_command in INTEGRATION_SUPPORTED_COMMANDS
    }

    for num in range(1, 25):
        command = f"outlet.{num!s}.load.on"
        list_commands_return_value[command] = command
        command = f"outlet.{num!s}.load.off"
        list_commands_return_value[command] = command

    ups_fixture = f"nut/{model}.json"
    list_vars = json.loads(load_fixture(ups_fixture))

    run_command = AsyncMock()

    await async_init_integration(
        hass,
        model,
        list_vars=list_vars,
        list_commands_return_value=list_commands_return_value,
        run_command=run_command,
    )

    entity_id = "switch.ups1_power_outlet_a1"
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"{unique_id_base}_outlet.1.load.poweronoff"

    switch = hass.states.get(entity_id)
    assert switch
    assert switch.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    run_command.assert_called_with("ups1", "outlet.1.load.off")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    run_command.assert_called_with("ups1", "outlet.1.load.on")

    switch = hass.states.get("switch.ups1_power_outlet_25")
    assert not switch

    switch = hass.states.get("switch.ups1_power_outlet_a25")
    assert not switch


async def test_switch_pdu_dynamic_outlets_state_unknown(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch entity with missing status is reported as unknown."""

    config_entry = await async_init_integration(
        hass,
        list_ups={"ups1": "UPS 1"},
        list_vars={
            "outlet.count": "1",
            "outlet.1.switchable": "yes",
            "outlet.1.name": "A1",
        },
        list_commands_return_value={
            "outlet.1.load.on": None,
            "outlet.1.load.off": None,
        },
    )

    entity_id = "switch.ups1_power_outlet_a1"
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"{config_entry.entry_id}_outlet.1.load.poweronoff"

    switch = hass.states.get(entity_id)
    assert switch
    assert switch.state == STATE_UNKNOWN
