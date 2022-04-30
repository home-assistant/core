"""Test button of ONVIF integration."""
from unittest.mock import AsyncMock

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.helpers import entity_registry as er

from . import MAC, setup_onvif_integration


async def test_reboot_button(hass):
    """Test states of the Reboot button."""
    await setup_onvif_integration(hass)

    state = hass.states.get("button.testcamera_reboot")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_DEVICE_CLASS) == ButtonDeviceClass.RESTART

    registry = er.async_get(hass)
    entry = registry.async_get("button.testcamera_reboot")
    assert entry
    assert entry.unique_id == f"{MAC}_reboot"


async def test_reboot_button_press(hass):
    """Test Reboot button press."""
    _, camera, _ = await setup_onvif_integration(hass)
    devicemgmt = camera.create_devicemgmt_service()
    devicemgmt.SystemReboot = AsyncMock(return_value=True)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        "press",
        {ATTR_ENTITY_ID: "button.testcamera_reboot"},
        blocking=True,
    )
    await hass.async_block_till_done()

    devicemgmt.SystemReboot.assert_called_once()
