"""Tests for the bosch_shc light platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant

from .conftest import (
    micromodule_dimmer_device,
    motion_detector2_device,
    setup_integration,
)


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the light platform."""
    with patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.LIGHT]):
        yield


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "micromodule_dimmers": [
                micromodule_dimmer_device(binarystate=True, brightness=100)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_dimmer_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The dimmer reports its on/off state and brightness."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.dimmer")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 255
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]


@pytest.mark.parametrize(
    "device_buckets",
    [{"micromodule_dimmers": [micromodule_dimmer_device()]}],
    indirect=True,
)
async def test_dimmer_turn_on_with_brightness(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Turning on with a brightness sets the level and switches the dimmer on."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.micromodule_dimmers[0]
    assert hass.states.get("light.dimmer").state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.dimmer", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    assert device.brightness == 50
    assert device.binarystate is True


@pytest.mark.parametrize(
    "device_buckets",
    [{"micromodule_dimmers": [micromodule_dimmer_device(binarystate=True)]}],
    indirect=True,
)
async def test_dimmer_turn_off(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Turning off clears the binary state."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.micromodule_dimmers[0]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.dimmer"},
        blocking=True,
    )

    assert device.binarystate is False


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "motion_detectors2": [
                motion_detector2_device(binaryswitch=True, multi_level_switch=50)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_motion_light_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The orientation light reports its on/off state and brightness."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.motion_detector_orientation_light")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors2": [motion_detector2_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_motion_light_turn_on_off(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Turning the orientation light on sets brightness and switch, off clears it."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.motion_detectors2[0]
    entity_id = "light.motion_detector_orientation_light"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    assert device.multi_level_switch == 100
    assert device.binaryswitch is True

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert device.binaryswitch is False
