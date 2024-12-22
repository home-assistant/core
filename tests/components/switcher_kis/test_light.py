"""Test the Switcher light platform."""

from unittest.mock import patch

from aioswitcher.api import SwitcherBaseResponse
from aioswitcher.device import DeviceState
import pytest

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from . import init_integration
from .consts import (
    DUMMY_DUAL_LIGHT_DEVICE as DEVICE4,
    DUMMY_DUAL_SHUTTER_SINGLE_LIGHT_DEVICE as DEVICE2,
    DUMMY_LIGHT_DEVICE as DEVICE3,
    DUMMY_SINGLE_SHUTTER_DUAL_LIGHT_DEVICE as DEVICE,
    DUMMY_TOKEN as TOKEN,
    DUMMY_TRIPLE_LIGHT_DEVICE as DEVICE5,
    DUMMY_USERNAME as USERNAME,
)

ENTITY_ID = f"{LIGHT_DOMAIN}.{slugify(DEVICE.name)}_light_1"
ENTITY_ID_2 = f"{LIGHT_DOMAIN}.{slugify(DEVICE.name)}_light_2"
ENTITY_ID2 = f"{LIGHT_DOMAIN}.{slugify(DEVICE2.name)}"
ENTITY_ID3 = f"{LIGHT_DOMAIN}.{slugify(DEVICE3.name)}"
ENTITY_ID4 = f"{LIGHT_DOMAIN}.{slugify(DEVICE4.name)}_light_1"
ENTITY_ID4_2 = f"{LIGHT_DOMAIN}.{slugify(DEVICE4.name)}_light_2"
ENTITY_ID5 = f"{LIGHT_DOMAIN}.{slugify(DEVICE5.name)}_light_1"
ENTITY_ID5_2 = f"{LIGHT_DOMAIN}.{slugify(DEVICE5.name)}_light_2"
ENTITY_ID5_3 = f"{LIGHT_DOMAIN}.{slugify(DEVICE5.name)}_light_3"


@pytest.mark.parametrize(
    ("device", "entity_id", "light_id", "device_state"),
    [
        (DEVICE, ENTITY_ID, 0, [DeviceState.OFF, DeviceState.ON]),
        (DEVICE, ENTITY_ID_2, 1, [DeviceState.ON, DeviceState.OFF]),
        (DEVICE2, ENTITY_ID2, 0, [DeviceState.OFF]),
        (DEVICE3, ENTITY_ID3, 0, [DeviceState.OFF]),
        (DEVICE4, ENTITY_ID4, 0, [DeviceState.OFF, DeviceState.ON]),
        (DEVICE4, ENTITY_ID4_2, 1, [DeviceState.ON, DeviceState.OFF]),
        (DEVICE5, ENTITY_ID5, 0, [DeviceState.OFF, DeviceState.ON, DeviceState.ON]),
        (DEVICE5, ENTITY_ID5_2, 1, [DeviceState.ON, DeviceState.OFF, DeviceState.ON]),
        (DEVICE5, ENTITY_ID5_3, 2, [DeviceState.ON, DeviceState.ON, DeviceState.OFF]),
    ],
)
@pytest.mark.parametrize(
    "mock_bridge", [[DEVICE, DEVICE2, DEVICE3, DEVICE4, DEVICE5]], indirect=True
)
async def test_light(
    hass: HomeAssistant,
    mock_bridge,
    mock_api,
    monkeypatch: pytest.MonkeyPatch,
    device,
    entity_id: str,
    light_id: int,
    device_state: list[DeviceState],
) -> None:
    """Test the light."""
    await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    # Test initial state - light on
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    # Test state change on --> off for light
    monkeypatch.setattr(device, "light", device_state)
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Test turning on light
    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.set_light",
    ) as mock_set_light:
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        assert mock_api.call_count == 2
        mock_set_light.assert_called_once_with(DeviceState.ON, light_id)
        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    # Test turning off light
    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.set_light"
    ) as mock_set_light:
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        assert mock_api.call_count == 4
        mock_set_light.assert_called_once_with(DeviceState.OFF, light_id)
        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("device", "entity_id", "light_id", "device_state"),
    [
        (DEVICE, ENTITY_ID, 0, [DeviceState.OFF, DeviceState.ON]),
        (DEVICE, ENTITY_ID_2, 1, [DeviceState.ON, DeviceState.OFF]),
        (DEVICE2, ENTITY_ID2, 0, [DeviceState.OFF]),
        (DEVICE3, ENTITY_ID3, 0, [DeviceState.OFF]),
        (DEVICE4, ENTITY_ID4, 0, [DeviceState.OFF, DeviceState.ON]),
        (DEVICE4, ENTITY_ID4_2, 1, [DeviceState.ON, DeviceState.OFF]),
        (DEVICE5, ENTITY_ID5, 0, [DeviceState.OFF, DeviceState.ON, DeviceState.ON]),
        (DEVICE5, ENTITY_ID5_2, 1, [DeviceState.ON, DeviceState.OFF, DeviceState.ON]),
        (DEVICE5, ENTITY_ID5_3, 2, [DeviceState.ON, DeviceState.ON, DeviceState.OFF]),
    ],
)
@pytest.mark.parametrize(
    "mock_bridge", [[DEVICE, DEVICE2, DEVICE3, DEVICE4, DEVICE5]], indirect=True
)
async def test_light_control_fail(
    hass: HomeAssistant,
    mock_bridge,
    mock_api,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    device,
    entity_id: str,
    light_id: int,
    device_state: list[DeviceState],
) -> None:
    """Test light control fail."""
    await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    # Test initial state - light off
    monkeypatch.setattr(device, "light", device_state)
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Test exception during turn on
    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.set_light",
        side_effect=RuntimeError("fake error"),
    ) as mock_control_device:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )

        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(DeviceState.ON, light_id)
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE

    # Make device available again
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Test error response during turn on
    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.set_light",
        return_value=SwitcherBaseResponse(None),
    ) as mock_control_device:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )

        assert mock_api.call_count == 4
        mock_control_device.assert_called_once_with(DeviceState.ON, light_id)
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE
