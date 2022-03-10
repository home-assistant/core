"""Test the update coordinator for HomeWizard."""

from unittest.mock import AsyncMock, patch

import homewizard_energy.models as models

from homeassistant.components import switch
from homeassistant.components.switch import DEVICE_CLASS_OUTLET, DEVICE_CLASS_SWITCH
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers import entity_registry as er


async def test_switch_entity_not_loaded_when_not_available(hass, init_integration):
    """Test entity loads smr version."""

    state_power_on = hass.states.get("sensor.product_name_aabbccddeeff_switch")
    state_switch_lock = hass.states.get("sensor.product_name_aabbccddeeff_switch_lock")

    assert state_power_on is None
    assert state_switch_lock is None


async def test_switch_loads_entities(hass, init_integration):
    """Test entity switches switch lock."""

    entity_registry = er.async_get(hass)

    state_power_on = hass.states.get("switch.product_name_aabbccddeeff_switch")
    entry_power_on = entity_registry.async_get(
        "switch.product_name_aabbccddeeff_switch"
    )
    assert state_power_on
    assert entry_power_on
    assert entry_power_on.unique_id == "aabbccddeeff_power_on"
    assert not entry_power_on.disabled
    assert state_power_on.state == STATE_ON
    assert (
        state_power_on.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Switch"
    )
    assert state_power_on.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_OUTLET
    assert ATTR_ICON not in state_power_on.attributes

    state_switch_lock = hass.states.get("switch.product_name_aabbccddeeff_switch_lock")
    entry_switch_lock = entity_registry.async_get(
        "switch.product_name_aabbccddeeff_switch_lock"
    )

    assert state_switch_lock
    assert entry_switch_lock
    assert entry_switch_lock.unique_id == "aabbccddeeff_switch_lock"
    assert not entry_switch_lock.disabled
    assert state_switch_lock.state == STATE_OFF
    assert (
        state_switch_lock.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Switch Lock"
    )
    assert state_switch_lock.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_SWITCH
    assert ATTR_ICON not in state_switch_lock.attributes


async def test_switch_power_on_off(hass, mock_config_entry, mock_homewizard_energy):
    """Test entity turns switch on and off."""

    # Prepare state mock
    state = models.State(True, False, None)

    def set_power_on(power_on):
        state.power_on = power_on

    mock_homewizard_energy.state = AsyncMock(return_value=state)
    mock_homewizard_energy.state_set = AsyncMock(side_effect=set_power_on)

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=mock_homewizard_energy,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("switch.product_name_aabbccddeeff_switch").state == STATE_ON

    # Turn power_on on
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": "switch.product_name_aabbccddeeff_switch"},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(mock_homewizard_energy.state_set.mock_calls) == 1
    assert hass.states.get("switch.product_name_aabbccddeeff_switch").state == STATE_OFF

    # Turn power_on off
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": "switch.product_name_aabbccddeeff_switch"},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert hass.states.get("switch.product_name_aabbccddeeff_switch").state == STATE_ON
    assert len(mock_homewizard_energy.state_set.mock_calls) == 2


async def test_switch_lock_on_off(hass, mock_config_entry, mock_homewizard_energy):
    """Test entity turns switch_lock on and off."""

    state = models.State(True, False, None)

    def set_switch_lock(switch_lock):
        state.switch_lock = switch_lock

    mock_homewizard_energy.state = AsyncMock(return_value=state)
    mock_homewizard_energy.state_set = AsyncMock(side_effect=set_switch_lock)

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=mock_homewizard_energy,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        hass.states.get("switch.product_name_aabbccddeeff_switch_lock").state
        == STATE_OFF
    )

    # Turn switch_lock on
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": "switch.product_name_aabbccddeeff_switch_lock"},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(mock_homewizard_energy.state_set.mock_calls) == 1
    assert (
        hass.states.get("switch.product_name_aabbccddeeff_switch_lock").state
        == STATE_ON
    )

    # Turn switch_lock off
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": "switch.product_name_aabbccddeeff_switch_lock"},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert (
        hass.states.get("switch.product_name_aabbccddeeff_switch_lock").state
        == STATE_OFF
    )
    assert len(mock_homewizard_energy.state_set.mock_calls) == 2


async def test_switch_lock_sets_power_on_available_state(
    hass, mock_config_entry, mock_homewizard_energy
):
    """Test switch_lock makes power_on unavailable."""

    state = models.State(True, False, None)

    def set_switch_lock(switch_lock):
        state.switch_lock = switch_lock

    mock_homewizard_energy.state = AsyncMock(return_value=state)
    mock_homewizard_energy.state_set = AsyncMock(side_effect=set_switch_lock)

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=mock_homewizard_energy,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        hass.states.get("switch.product_name_aabbccddeeff_switch_lock").state
        == STATE_OFF
    )
    assert hass.states.get("switch.product_name_aabbccddeeff_switch").state == STATE_ON

    # Turn switch_lock on
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": "switch.product_name_aabbccddeeff_switch_lock"},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(mock_homewizard_energy.state_set.mock_calls) == 1
    assert (
        hass.states.get("switch.product_name_aabbccddeeff_switch_lock").state
        == STATE_ON
    )
    assert (
        hass.states.get("switch.product_name_aabbccddeeff_switch").state
        == STATE_UNAVAILABLE
    )

    # Turn switch_lock off
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": "switch.product_name_aabbccddeeff_switch_lock"},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert (
        hass.states.get("switch.product_name_aabbccddeeff_switch_lock").state
        == STATE_OFF
    )
    assert hass.states.get("switch.product_name_aabbccddeeff_switch").state == STATE_ON
    assert len(mock_homewizard_energy.state_set.mock_calls) == 2
