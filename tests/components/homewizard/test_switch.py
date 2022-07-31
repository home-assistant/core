"""Test the update coordinator for HomeWizard."""

from unittest.mock import AsyncMock, patch

from homewizard_energy.models import State

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

from .generator import get_mock_device


async def test_switch_entity_not_loaded_when_not_available(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads smr version."""

    api = get_mock_device()

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state_power_on = hass.states.get("sensor.product_name_aabbccddeeff")
    state_switch_lock = hass.states.get("sensor.product_name_aabbccddeeff_switch_lock")

    assert state_power_on is None
    assert state_switch_lock is None


async def test_switch_loads_entities(hass, mock_config_entry_data, mock_config_entry):
    """Test entity loads smr version."""

    api = get_mock_device()
    api.state = AsyncMock(
        return_value=State.from_dict({"power_on": False, "switch_lock": False})
    )

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state_power_on = hass.states.get("switch.product_name_aabbccddeeff")
    entry_power_on = entity_registry.async_get("switch.product_name_aabbccddeeff")
    assert state_power_on
    assert entry_power_on
    assert entry_power_on.unique_id == "aabbccddeeff_power_on"
    assert not entry_power_on.disabled
    assert state_power_on.state == STATE_OFF
    assert (
        state_power_on.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff)"
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
        == "Product Name (aabbccddeeff) Switch lock"
    )
    assert state_switch_lock.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_SWITCH
    assert ATTR_ICON not in state_switch_lock.attributes


async def test_switch_power_on_off(hass, mock_config_entry_data, mock_config_entry):
    """Test entity turns switch on and off."""

    api = get_mock_device()
    api.state = AsyncMock(
        return_value=State.from_dict({"power_on": False, "switch_lock": False})
    )

    def state_set(power_on):
        api.state = AsyncMock(
            return_value=State.from_dict({"power_on": power_on, "switch_lock": False})
        )

    api.state_set = AsyncMock(side_effect=state_set)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get("switch.product_name_aabbccddeeff").state == STATE_OFF

        # Turn power_on on
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": "switch.product_name_aabbccddeeff"},
            blocking=True,
        )

        await hass.async_block_till_done()
        assert len(api.state_set.mock_calls) == 1
        assert hass.states.get("switch.product_name_aabbccddeeff").state == STATE_ON

        # Turn power_on off
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_OFF,
            {"entity_id": "switch.product_name_aabbccddeeff"},
            blocking=True,
        )

        await hass.async_block_till_done()
        assert hass.states.get("switch.product_name_aabbccddeeff").state == STATE_OFF
        assert len(api.state_set.mock_calls) == 2


async def test_switch_lock_power_on_off(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity turns switch on and off."""

    api = get_mock_device()
    api.state = AsyncMock(
        return_value=State.from_dict({"power_on": False, "switch_lock": False})
    )

    def state_set(switch_lock):
        api.state = AsyncMock(
            return_value=State.from_dict({"power_on": True, "switch_lock": switch_lock})
        )

    api.state_set = AsyncMock(side_effect=state_set)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert (
            hass.states.get("switch.product_name_aabbccddeeff_switch_lock").state
            == STATE_OFF
        )

        # Turn power_on on
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": "switch.product_name_aabbccddeeff_switch_lock"},
            blocking=True,
        )

        await hass.async_block_till_done()
        assert len(api.state_set.mock_calls) == 1
        assert (
            hass.states.get("switch.product_name_aabbccddeeff_switch_lock").state
            == STATE_ON
        )

        # Turn power_on off
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
        assert len(api.state_set.mock_calls) == 2


async def test_switch_lock_sets_power_on_unavailable(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity turns switch on and off."""

    api = get_mock_device()
    api.state = AsyncMock(
        return_value=State.from_dict({"power_on": True, "switch_lock": False})
    )

    def state_set(switch_lock):
        api.state = AsyncMock(
            return_value=State.from_dict({"power_on": True, "switch_lock": switch_lock})
        )

    api.state_set = AsyncMock(side_effect=state_set)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get("switch.product_name_aabbccddeeff").state == STATE_ON
        assert (
            hass.states.get("switch.product_name_aabbccddeeff_switch_lock").state
            == STATE_OFF
        )

        # Turn power_on on
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": "switch.product_name_aabbccddeeff_switch_lock"},
            blocking=True,
        )

        await hass.async_block_till_done()
        assert len(api.state_set.mock_calls) == 1
        assert (
            hass.states.get("switch.product_name_aabbccddeeff").state
            == STATE_UNAVAILABLE
        )
        assert (
            hass.states.get("switch.product_name_aabbccddeeff_switch_lock").state
            == STATE_ON
        )

        # Turn power_on off
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_OFF,
            {"entity_id": "switch.product_name_aabbccddeeff_switch_lock"},
            blocking=True,
        )

        await hass.async_block_till_done()
        assert hass.states.get("switch.product_name_aabbccddeeff").state == STATE_ON
        assert (
            hass.states.get("switch.product_name_aabbccddeeff_switch_lock").state
            == STATE_OFF
        )
        assert len(api.state_set.mock_calls) == 2
