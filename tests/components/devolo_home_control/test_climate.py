"""Tests for the devolo spencer Control climate."""
from unittest.mock import patch

from spencerassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from spencerassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
)
from spencerassistant.core import spencerAssistant

from . import configure_integration
from .mocks import spencerControlMock, spencerControlMockClimate


async def test_climate(hass: spencerAssistant):
    """Test setup and state change of a climate device."""
    entry = configure_integration(hass)
    test_gateway = spencerControlMockClimate()
    test_gateway.devices["Test"].value = 20
    with patch(
        "spencerassistant.components.devolo_spencer_control.spencerControl",
        side_effect=[test_gateway, spencerControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{DOMAIN}.test")
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == test_gateway.devices["Test"].value
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Test"

    # Emulate websocket message: temperature changed
    test_gateway.publisher.dispatch("Test", ("Test", 21.0))
    await hass.async_block_till_done()
    state = hass.states.get(f"{DOMAIN}.test")
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 21.0

    # Test setting temperature
    with patch(
        "devolo_spencer_control_api.properties.multi_level_switch_property.MultiLevelSwitchProperty.set"
    ) as set_value:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: f"{DOMAIN}.test",
                ATTR_HVAC_MODE: HVACMode.HEAT,
                ATTR_TEMPERATURE: 20.0,
            },
            blocking=True,
        )  # In reality, this leads to a websocket message like already tested above
        set_value.assert_called_once_with(20.0)

    # Emulate websocket message: device went offline
    test_gateway.devices["Test"].status = 1
    test_gateway.publisher.dispatch("Test", ("Status", False, "status"))
    await hass.async_block_till_done()
    assert hass.states.get(f"{DOMAIN}.test").state == STATE_UNAVAILABLE


async def test_remove_from_hass(hass: spencerAssistant):
    """Test removing entity."""
    entry = configure_integration(hass)
    test_gateway = spencerControlMockClimate()
    with patch(
        "spencerassistant.components.devolo_spencer_control.spencerControl",
        side_effect=[test_gateway, spencerControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{DOMAIN}.test")
    assert state is not None
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert test_gateway.publisher.unregister.call_count == 2
