"""Test HomematicIP Cloud valve entities."""

from homeassistant.components.valve import SERVICE_OPEN_VALVE, ValveState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .helper import HomeFactory, async_manipulate_test_data, get_and_check_entity_basics


async def test_watering_valve(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicIP watering valve."""
    entity_id = "valve.bewaesserungsaktor_watering"
    entity_name = "Bewaesserungsaktor watering"
    device_model = "ELV-SH-WSM"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Bewaesserungsaktor"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == ValveState.CLOSED

    await hass.services.async_call(
        Platform.VALVE, SERVICE_OPEN_VALVE, {"entity_id": entity_id}, blocking=True
    )

    await async_manipulate_test_data(
        hass, hmip_device, "wateringActive", True, channel=1
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == ValveState.OPEN
