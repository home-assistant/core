"""Test switch platform of ONVIF integration."""

from unittest.mock import AsyncMock

from onvif.exceptions import ONVIFError
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MAC, Capabilities, setup_onvif_integration


async def test_wiper_switch(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test states of the Wiper switch."""
    await setup_onvif_integration(hass)

    state = hass.states.get("switch.testcamera_wiper")
    assert state
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get("switch.testcamera_wiper")
    assert entry
    assert entry.unique_id == f"{MAC}_wiper"


async def test_wiper_switch_no_ptz(hass: HomeAssistant) -> None:
    """Test the wiper switch does not get created if the camera does not support ptz."""
    await setup_onvif_integration(
        hass, capabilities=Capabilities(imaging=True, ptz=False)
    )

    assert hass.states.get("switch.testcamera_wiper") is None


async def test_wiper_switch_with_ptz_only(hass: HomeAssistant) -> None:
    """Test the wiper switch gets created for PTZ-only devices."""
    await setup_onvif_integration(
        hass, capabilities=Capabilities(imaging=False, ptz=True, deviceio=False)
    )

    state = hass.states.get("switch.testcamera_wiper")
    assert state
    assert state.state == STATE_UNKNOWN


async def test_turn_wiper_switch_on(hass: HomeAssistant) -> None:
    """Test Wiper switch turn on."""
    _, _camera, device = await setup_onvif_integration(hass)
    device.async_run_aux_command = AsyncMock(return_value=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: "switch.testcamera_wiper"},
        blocking=True,
    )
    await hass.async_block_till_done()

    device.async_run_aux_command.assert_called_once()
    state = hass.states.get("switch.testcamera_wiper")
    assert state.state == STATE_ON


async def test_turn_wiper_switch_off(hass: HomeAssistant) -> None:
    """Test Wiper switch turn off."""
    _, _camera, device = await setup_onvif_integration(hass)
    device.async_run_aux_command = AsyncMock(return_value=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: "switch.testcamera_wiper"},
        blocking=True,
    )
    await hass.async_block_till_done()

    device.async_run_aux_command.assert_called_once()
    state = hass.states.get("switch.testcamera_wiper")
    assert state.state == STATE_OFF


async def test_autofocus_switch(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test states of the autofocus switch."""
    await setup_onvif_integration(hass)

    state = hass.states.get("switch.testcamera_autofocus")
    assert state
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get("switch.testcamera_autofocus")
    assert entry
    assert entry.unique_id == f"{MAC}_autofocus"


async def test_auto_focus_switch_no_imaging(hass: HomeAssistant) -> None:
    """Test the autofocus switch does not get created if the camera does not support imaging."""
    await setup_onvif_integration(
        hass, capabilities=Capabilities(imaging=False, ptz=True)
    )

    assert hass.states.get("switch.testcamera_autofocus") is None


async def test_turn_autofocus_switch_on(hass: HomeAssistant) -> None:
    """Test autofocus switch turn on."""
    _, _camera, device = await setup_onvif_integration(hass)
    device.async_set_imaging_settings = AsyncMock(return_value=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: "switch.testcamera_autofocus"},
        blocking=True,
    )
    await hass.async_block_till_done()

    device.async_set_imaging_settings.assert_called_once()
    state = hass.states.get("switch.testcamera_autofocus")
    assert state.state == STATE_ON


async def test_turn_autofocus_switch_off(hass: HomeAssistant) -> None:
    """Test autofocus switch turn off."""
    _, _camera, device = await setup_onvif_integration(hass)
    device.async_set_imaging_settings = AsyncMock(return_value=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: "switch.testcamera_autofocus"},
        blocking=True,
    )
    await hass.async_block_till_done()

    device.async_set_imaging_settings.assert_called_once()
    state = hass.states.get("switch.testcamera_autofocus")
    assert state.state == STATE_OFF


async def test_infrared_switch(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test states of the autofocus switch."""
    await setup_onvif_integration(hass)

    state = hass.states.get("switch.testcamera_ir_lamp")
    assert state
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get("switch.testcamera_ir_lamp")
    assert entry
    assert entry.unique_id == f"{MAC}_ir_lamp"


async def test_infrared_switch_no_imaging(hass: HomeAssistant) -> None:
    """Test the infrared switch does not get created if the camera does not support imaging."""
    await setup_onvif_integration(
        hass, capabilities=Capabilities(imaging=False, ptz=False)
    )

    assert hass.states.get("switch.testcamera_ir_lamp") is None


async def test_turn_infrared_switch_on(hass: HomeAssistant) -> None:
    """Test infrared switch turn on."""
    _, _camera, device = await setup_onvif_integration(hass)
    device.async_set_imaging_settings = AsyncMock(return_value=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: "switch.testcamera_ir_lamp"},
        blocking=True,
    )
    await hass.async_block_till_done()

    device.async_set_imaging_settings.assert_called_once()
    state = hass.states.get("switch.testcamera_ir_lamp")
    assert state.state == STATE_ON


async def test_turn_infrared_switch_off(hass: HomeAssistant) -> None:
    """Test infrared switch turn off."""
    _, _camera, device = await setup_onvif_integration(hass)
    device.async_set_imaging_settings = AsyncMock(return_value=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: "switch.testcamera_ir_lamp"},
        blocking=True,
    )
    await hass.async_block_till_done()

    device.async_set_imaging_settings.assert_called_once()
    state = hass.states.get("switch.testcamera_ir_lamp")
    assert state.state == STATE_OFF


async def test_relay_switch(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test states of the relay switch."""
    await setup_onvif_integration(
        hass, capabilities=Capabilities(deviceio=True, relay_outputs=2)
    )

    # Check first relay
    state = hass.states.get("switch.testcamera_relay_relayoutputtoken_0")
    assert state
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get("switch.testcamera_relay_relayoutputtoken_0")
    assert entry
    assert entry.unique_id == f"{MAC}_relay_RelayOutputToken_0"

    # Check second relay
    state = hass.states.get("switch.testcamera_relay_relayoutputtoken_1")
    assert state
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get("switch.testcamera_relay_relayoutputtoken_1")
    assert entry
    assert entry.unique_id == f"{MAC}_relay_RelayOutputToken_1"


async def test_relay_switch_no_deviceio(hass: HomeAssistant) -> None:
    """Test the relay switch does not get created if the camera does not support DeviceIO."""
    await setup_onvif_integration(
        hass, capabilities=Capabilities(deviceio=False, relay_outputs=0)
    )

    assert hass.states.get("switch.testcamera_relay_relayoutputtoken_0") is None


async def test_relay_switch_fetches_relays_when_count_is_zero(
    hass: HomeAssistant,
) -> None:
    """Test relay discovery still runs when the reported count is zero."""
    _, _camera, device = await setup_onvif_integration(
        hass, capabilities=Capabilities(deviceio=True, relay_outputs=0)
    )

    device.async_get_relay_outputs.assert_awaited_once()


async def test_turn_relay_switch_on(hass: HomeAssistant) -> None:
    """Test relay switch turn on."""
    _, _camera, device = await setup_onvif_integration(
        hass, capabilities=Capabilities(deviceio=True, relay_outputs=1)
    )
    device.async_set_relay_output_state = AsyncMock(return_value=None)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: "switch.testcamera_relay_relayoutputtoken_0"},
        blocking=True,
    )
    await hass.async_block_till_done()

    device.async_set_relay_output_state.assert_called_once_with(
        "RelayOutputToken_0", "active"
    )
    state = hass.states.get("switch.testcamera_relay_relayoutputtoken_0")
    assert state.state == STATE_ON


async def test_turn_relay_switch_off(hass: HomeAssistant) -> None:
    """Test relay switch turn off."""
    _, _camera, device = await setup_onvif_integration(
        hass, capabilities=Capabilities(deviceio=True, relay_outputs=1)
    )
    device.async_set_relay_output_state = AsyncMock(return_value=None)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: "switch.testcamera_relay_relayoutputtoken_0"},
        blocking=True,
    )
    await hass.async_block_till_done()

    device.async_set_relay_output_state.assert_called_once_with(
        "RelayOutputToken_0", "inactive"
    )
    state = hass.states.get("switch.testcamera_relay_relayoutputtoken_0")
    assert state.state == STATE_OFF


async def test_relay_switch_error_handling(hass: HomeAssistant) -> None:
    """Test relay switch error handling reverts state."""
    _, _camera, device = await setup_onvif_integration(
        hass, capabilities=Capabilities(deviceio=True, relay_outputs=1)
    )
    device.async_set_relay_output_state = AsyncMock(
        side_effect=ONVIFError("Test error")
    )

    with pytest.raises(ONVIFError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_on",
            {ATTR_ENTITY_ID: "switch.testcamera_relay_relayoutputtoken_0"},
            blocking=True,
        )

    # State should remain unknown (not changed to on)
    state = hass.states.get("switch.testcamera_relay_relayoutputtoken_0")
    assert state.state == STATE_UNKNOWN


async def test_relay_switch_turn_off_error_handling(hass: HomeAssistant) -> None:
    """Test relay switch turn_off error handling reverts state."""
    _, _camera, device = await setup_onvif_integration(
        hass, capabilities=Capabilities(deviceio=True, relay_outputs=1)
    )

    # First turn on the relay
    device.async_set_relay_output_state = AsyncMock(return_value=None)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: "switch.testcamera_relay_relayoutputtoken_0"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify it's on
    state = hass.states.get("switch.testcamera_relay_relayoutputtoken_0")
    assert state.state == STATE_ON

    # Now make turn_off fail
    device.async_set_relay_output_state = AsyncMock(
        side_effect=ONVIFError("Test error")
    )

    with pytest.raises(ONVIFError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_off",
            {ATTR_ENTITY_ID: "switch.testcamera_relay_relayoutputtoken_0"},
            blocking=True,
        )

    # State should remain on (not changed to off)
    state = hass.states.get("switch.testcamera_relay_relayoutputtoken_0")
    assert state.state == STATE_ON
