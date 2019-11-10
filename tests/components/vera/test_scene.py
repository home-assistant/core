"""Vera tests."""

from homeassistant.core import HomeAssistant

from .common import (
    DEVICE_SCENE_CONTROLLER_ID,
    RESPONSE_LU_SDATA_EMPTY,
    RESPONSE_SDATA,
    RESPONSE_STATUS,
    assert_state,
    async_call_service,
    async_configure_component,
)


async def test_scene(hass: HomeAssistant) -> None:
    """Test function."""
    component_data = await async_configure_component(
        hass=hass,
        response_sdata=RESPONSE_SDATA,
        response_status=RESPONSE_STATUS,
        respone_lu_sdata=RESPONSE_LU_SDATA_EMPTY,
    )

    # Scene
    # Possible bug. Using the service against a scene does not result in an API call.
    await async_call_service(
        hass, component_data, DEVICE_SCENE_CONTROLLER_ID, "scene", "turn_on"
    )
    assert_state(hass, component_data, DEVICE_SCENE_CONTROLLER_ID, "switch", "off")
