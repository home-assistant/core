"""Tests for the WiLight integration."""
from asynctest import patch
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
from homeassistant.helpers.typing import HomeAssistantType

from tests.components.wilight import (
    HOST,
    UPNP_MAC_ADDRESS,
    UPNP_MODEL_NAME,
    UPNP_MODEL_NAME_COLOR,
    UPNP_MODEL_NAME_DIMMER,
    UPNP_MODEL_NUMBER,
    UPNP_SERIAL,
    setup_integration,
)


@pytest.fixture(name="dummy_create_api_device_pb")
def mock_dummy_create_api_device_pb():
    """Mock a valid api_devce."""

    device = pywilight.discovery.wilight_from_discovery(
        f"http://{HOST}:45995/wilight.xml",
        UPNP_MAC_ADDRESS,
        UPNP_MODEL_NAME,
        UPNP_SERIAL,
        UPNP_MODEL_NUMBER,
    )

    device.set_dummy(True)

    with patch(
        "homeassistant.components.wilight.parent_device.create_api_device",
        return_value=device,
    ):
        yield device


@pytest.fixture(name="dummy_create_api_device_dimmer")
def mock_dummy_create_api_device_dimmer():
    """Mock a valid api_devce."""

    device = pywilight.discovery.wilight_from_discovery(
        f"http://{HOST}:45995/wilight.xml",
        UPNP_MAC_ADDRESS,
        UPNP_MODEL_NAME_DIMMER,
        UPNP_SERIAL,
        UPNP_MODEL_NUMBER,
    )

    device.set_dummy(True)

    with patch(
        "homeassistant.components.wilight.parent_device.create_api_device",
        return_value=device,
    ):
        yield device


@pytest.fixture(name="dummy_create_api_device_color")
def mock_dummy_create_api_device_color():
    """Mock a valid api_devce."""

    device = pywilight.discovery.wilight_from_discovery(
        f"http://{HOST}:45995/wilight.xml",
        UPNP_MAC_ADDRESS,
        UPNP_MODEL_NAME_COLOR,
        UPNP_SERIAL,
        UPNP_MODEL_NUMBER,
    )

    device.set_dummy(True)

    with patch(
        "homeassistant.components.wilight.parent_device.create_api_device",
        return_value=device,
    ):
        yield device


async def test_on_off_light_state(
    hass: HomeAssistantType, dummy_create_api_device_pb
) -> None:
    """Test the WiLight configuration entry unloading."""
    entry = await setup_integration(hass)
    assert entry
    assert entry.unique_id == "WL000000000099"

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # First segment of the strip
    state = hass.states.get("light.wl000000000099_1")
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get("light.wl000000000099_1")
    assert entry
    assert entry.unique_id == "WL000000000099_0"


async def test_dimmer_light_state(
    hass: HomeAssistantType, dummy_create_api_device_dimmer
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


async def test_color_light_state(
    hass: HomeAssistantType, dummy_create_api_device_color
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
