"""The button tests for the Mazda Connected Services integration."""

from pymazda import MazdaException
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_button_setup_non_electric_vehicle(hass) -> None:
    """Test creation of button entities."""
    await init_integration(hass)

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("button.my_mazda3_start_engine")
    assert entry
    assert entry.unique_id == "JM000000000000000_start_engine"
    state = hass.states.get("button.my_mazda3_start_engine")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Start engine"
    assert state.attributes.get(ATTR_ICON) == "mdi:engine"

    entry = entity_registry.async_get("button.my_mazda3_stop_engine")
    assert entry
    assert entry.unique_id == "JM000000000000000_stop_engine"
    state = hass.states.get("button.my_mazda3_stop_engine")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Stop engine"
    assert state.attributes.get(ATTR_ICON) == "mdi:engine-off"

    entry = entity_registry.async_get("button.my_mazda3_turn_on_hazard_lights")
    assert entry
    assert entry.unique_id == "JM000000000000000_turn_on_hazard_lights"
    state = hass.states.get("button.my_mazda3_turn_on_hazard_lights")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Turn on hazard lights"
    assert state.attributes.get(ATTR_ICON) == "mdi:hazard-lights"

    entry = entity_registry.async_get("button.my_mazda3_turn_off_hazard_lights")
    assert entry
    assert entry.unique_id == "JM000000000000000_turn_off_hazard_lights"
    state = hass.states.get("button.my_mazda3_turn_off_hazard_lights")
    assert state
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Turn off hazard lights"
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:hazard-lights"

    # Since this is a non-electric vehicle, electric vehicle buttons should not be created
    entry = entity_registry.async_get("button.my_mazda3_refresh_vehicle_status")
    assert entry is None
    state = hass.states.get("button.my_mazda3_refresh_vehicle_status")
    assert state is None


async def test_button_setup_electric_vehicle(hass) -> None:
    """Test creation of button entities for an electric vehicle."""
    await init_integration(hass, electric_vehicle=True)

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("button.my_mazda3_start_engine")
    assert entry
    assert entry.unique_id == "JM000000000000000_start_engine"
    state = hass.states.get("button.my_mazda3_start_engine")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Start engine"
    assert state.attributes.get(ATTR_ICON) == "mdi:engine"

    entry = entity_registry.async_get("button.my_mazda3_stop_engine")
    assert entry
    assert entry.unique_id == "JM000000000000000_stop_engine"
    state = hass.states.get("button.my_mazda3_stop_engine")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Stop engine"
    assert state.attributes.get(ATTR_ICON) == "mdi:engine-off"

    entry = entity_registry.async_get("button.my_mazda3_turn_on_hazard_lights")
    assert entry
    assert entry.unique_id == "JM000000000000000_turn_on_hazard_lights"
    state = hass.states.get("button.my_mazda3_turn_on_hazard_lights")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Turn on hazard lights"
    assert state.attributes.get(ATTR_ICON) == "mdi:hazard-lights"

    entry = entity_registry.async_get("button.my_mazda3_turn_off_hazard_lights")
    assert entry
    assert entry.unique_id == "JM000000000000000_turn_off_hazard_lights"
    state = hass.states.get("button.my_mazda3_turn_off_hazard_lights")
    assert state
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Turn off hazard lights"
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:hazard-lights"

    entry = entity_registry.async_get("button.my_mazda3_refresh_status")
    assert entry
    assert entry.unique_id == "JM000000000000000_refresh_vehicle_status"
    state = hass.states.get("button.my_mazda3_refresh_status")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Refresh status"
    assert state.attributes.get(ATTR_ICON) == "mdi:refresh"


@pytest.mark.parametrize(
    "entity_id_suffix, api_method_name",
    [
        ("start_engine", "start_engine"),
        ("stop_engine", "stop_engine"),
        ("turn_on_hazard_lights", "turn_on_hazard_lights"),
        ("turn_off_hazard_lights", "turn_off_hazard_lights"),
        ("refresh_status", "refresh_vehicle_status"),
    ],
)
async def test_button_press(hass, entity_id_suffix, api_method_name) -> None:
    """Test pressing the button entities."""
    client_mock = await init_integration(hass, electric_vehicle=True)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: f"button.my_mazda3_{entity_id_suffix}"},
        blocking=True,
    )
    await hass.async_block_till_done()

    api_method = getattr(client_mock, api_method_name)
    api_method.assert_called_once_with(12345)


async def test_button_press_error(hass) -> None:
    """Test the Mazda API raising an error when a button entity is pressed."""
    client_mock = await init_integration(hass)

    client_mock.start_engine.side_effect = MazdaException("Test error")

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.my_mazda3_start_engine"},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert str(err.value) == "Test error"
