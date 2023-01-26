"""Tests for the WiLight integration."""
from unittest.mock import patch

import pytest
import pywilight

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    HOST,
    UPNP_MAC_ADDRESS,
    UPNP_MODEL_NAME_COLOR,
    UPNP_MODEL_NAME_DIMMER,
    UPNP_MODEL_NAME_LIGHT_FAN,
    UPNP_MODEL_NAME_P_B,
    UPNP_MODEL_NUMBER,
    UPNP_SERIAL,
    WILIGHT_ID,
    setup_integration,
)


@pytest.fixture(name="dummy_get_components_from_model_light")
def mock_dummy_get_components_from_model_light():
    """Mock a components list with light."""
    components = ["light"]
    with patch(
        "pywilight.get_components_from_model",
        return_value=components,
    ):
        yield components


@pytest.fixture(name="dummy_device_from_host_light_fan")
def mock_dummy_device_from_host_light_fan():
    """Mock a valid api_devce."""

    device = pywilight.wilight_from_discovery(
        f"http://{HOST}:45995/wilight.xml",
        UPNP_MAC_ADDRESS,
        UPNP_MODEL_NAME_LIGHT_FAN,
        UPNP_SERIAL,
        UPNP_MODEL_NUMBER,
    )

    device.set_dummy(True)

    with patch(
        "pywilight.device_from_host",
        return_value=device,
    ):
        yield device


@pytest.fixture(name="dummy_device_from_host_pb")
def mock_dummy_device_from_host_pb():
    """Mock a valid api_devce."""

    device = pywilight.wilight_from_discovery(
        f"http://{HOST}:45995/wilight.xml",
        UPNP_MAC_ADDRESS,
        UPNP_MODEL_NAME_P_B,
        UPNP_SERIAL,
        UPNP_MODEL_NUMBER,
    )

    device.set_dummy(True)

    with patch(
        "pywilight.device_from_host",
        return_value=device,
    ):
        yield device


@pytest.fixture(name="dummy_device_from_host_dimmer")
def mock_dummy_device_from_host_dimmer():
    """Mock a valid api_devce."""

    device = pywilight.wilight_from_discovery(
        f"http://{HOST}:45995/wilight.xml",
        UPNP_MAC_ADDRESS,
        UPNP_MODEL_NAME_DIMMER,
        UPNP_SERIAL,
        UPNP_MODEL_NUMBER,
    )

    device.set_dummy(True)

    with patch(
        "pywilight.device_from_host",
        return_value=device,
    ):
        yield device


@pytest.fixture(name="dummy_device_from_host_color")
def mock_dummy_device_from_host_color():
    """Mock a valid api_devce."""

    device = pywilight.wilight_from_discovery(
        f"http://{HOST}:45995/wilight.xml",
        UPNP_MAC_ADDRESS,
        UPNP_MODEL_NAME_COLOR,
        UPNP_SERIAL,
        UPNP_MODEL_NUMBER,
    )

    device.set_dummy(True)

    with patch(
        "pywilight.device_from_host",
        return_value=device,
    ):
        yield device


async def test_loading_light(
    hass: HomeAssistant,
    dummy_device_from_host_light_fan,
    dummy_get_components_from_model_light,
) -> None:
    """Test the WiLight configuration entry loading."""

    # Using light_fan and removind fan from get_components_from_model
    # to test light.py line 28
    entry = await setup_integration(hass)
    assert entry
    assert entry.unique_id == WILIGHT_ID

    entity_registry = er.async_get(hass)

    # First segment of the strip
    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get("light.wl000000000099_1")
    assert entry
    assert entry.unique_id == "WL000000000099_0"


async def test_on_off_light_state(
    hass: HomeAssistant, dummy_device_from_host_pb
) -> None:
    """Test the change of state of the light switches."""
    await setup_integration(hass)

    # Turn on
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.wl000000000099_1"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_ON

    # Turn off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.wl000000000099_1"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_OFF


async def test_dimmer_light_state(
    hass: HomeAssistant, dummy_device_from_host_dimmer
) -> None:
    """Test the change of state of the light switches."""
    await setup_integration(hass)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_BRIGHTNESS: 42, ATTR_ENTITY_ID: "light.wl000000000099_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 42

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_BRIGHTNESS: 0, ATTR_ENTITY_ID: "light.wl000000000099_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_BRIGHTNESS: 100, ATTR_ENTITY_ID: "light.wl000000000099_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 100

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.wl000000000099_1"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_OFF

    # Turn on
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.wl000000000099_1"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_ON


async def test_color_light_state(
    hass: HomeAssistant, dummy_device_from_host_color
) -> None:
    """Test the change of state of the light switches."""
    await setup_integration(hass)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_BRIGHTNESS: 42,
            ATTR_HS_COLOR: [0, 100],
            ATTR_ENTITY_ID: "light.wl000000000099_1",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 42
    state_color = [
        round(state.attributes.get(ATTR_HS_COLOR)[0]),
        round(state.attributes.get(ATTR_HS_COLOR)[1]),
    ]
    assert state_color == [0, 100]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_BRIGHTNESS: 0, ATTR_ENTITY_ID: "light.wl000000000099_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_BRIGHTNESS: 100,
            ATTR_HS_COLOR: [270, 50],
            ATTR_ENTITY_ID: "light.wl000000000099_1",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 100
    state_color = [
        round(state.attributes.get(ATTR_HS_COLOR)[0]),
        round(state.attributes.get(ATTR_HS_COLOR)[1]),
    ]
    assert state_color == [270, 50]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.wl000000000099_1"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_OFF

    # Turn on
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.wl000000000099_1"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_ON

    # Hue = 0, Saturation = 100
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_HS_COLOR: [0, 100], ATTR_ENTITY_ID: "light.wl000000000099_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_ON
    state_color = [
        round(state.attributes.get(ATTR_HS_COLOR)[0]),
        round(state.attributes.get(ATTR_HS_COLOR)[1]),
    ]
    assert state_color == [0, 100]

    # Brightness = 60
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_BRIGHTNESS: 60, ATTR_ENTITY_ID: "light.wl000000000099_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 60
