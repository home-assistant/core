"""Tests for the WiLight integration."""

from unittest.mock import patch

import pytest
import pywilight

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.wilight import DOMAIN as WILIGHT_DOMAIN
from homeassistant.components.wilight.switch import (
    ATTR_PAUSE_TIME,
    ATTR_TRIGGER,
    ATTR_TRIGGER_1,
    ATTR_TRIGGER_2,
    ATTR_TRIGGER_3,
    ATTR_TRIGGER_4,
    ATTR_TRIGGER_INDEX,
    ATTR_WATERING_TIME,
    SERVICE_SET_PAUSE_TIME,
    SERVICE_SET_TRIGGER,
    SERVICE_SET_WATERING_TIME,
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
    UPNP_MODEL_NAME_SWITCH,
    UPNP_MODEL_NUMBER,
    UPNP_SERIAL,
    WILIGHT_ID,
    setup_integration,
)


@pytest.fixture(name="dummy_device_from_host_switch")
def mock_dummy_device_from_host_switch():
    """Mock a valid api_devce."""

    device = pywilight.wilight_from_discovery(
        f"http://{HOST}:45995/wilight.xml",
        UPNP_MAC_ADDRESS,
        UPNP_MODEL_NAME_SWITCH,
        UPNP_SERIAL,
        UPNP_MODEL_NUMBER,
    )

    device.set_dummy(True)

    with patch(
        "pywilight.device_from_host",
        return_value=device,
    ):
        yield device


async def test_loading_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    dummy_device_from_host_switch,
) -> None:
    """Test the WiLight configuration entry loading."""

    entry = await setup_integration(hass)
    assert entry
    assert entry.unique_id == WILIGHT_ID

    # First segment of the strip
    state = hass.states.get("switch.wl000000000099_1_watering")
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get("switch.wl000000000099_1_watering")
    assert entry
    assert entry.unique_id == "WL000000000099_0"

    # Seconnd segment of the strip
    state = hass.states.get("switch.wl000000000099_2_pause")
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get("switch.wl000000000099_2_pause")
    assert entry
    assert entry.unique_id == "WL000000000099_1"


async def test_on_off_switch_state(
    hass: HomeAssistant, dummy_device_from_host_switch
) -> None:
    """Test the change of state of the switch."""
    await setup_integration(hass)

    # On - watering
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.wl000000000099_1_watering"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.wl000000000099_1_watering")
    assert state
    assert state.state == STATE_ON

    # Off - watering
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.wl000000000099_1_watering"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.wl000000000099_1_watering")
    assert state
    assert state.state == STATE_OFF

    # On - pause
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.wl000000000099_2_pause"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.wl000000000099_2_pause")
    assert state
    assert state.state == STATE_ON

    # Off - pause
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.wl000000000099_2_pause"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.wl000000000099_2_pause")
    assert state
    assert state.state == STATE_OFF


async def test_switch_services(
    hass: HomeAssistant, dummy_device_from_host_switch
) -> None:
    """Test the services of the switch."""
    await setup_integration(hass)

    # Set watering time
    await hass.services.async_call(
        WILIGHT_DOMAIN,
        SERVICE_SET_WATERING_TIME,
        {ATTR_WATERING_TIME: 30, ATTR_ENTITY_ID: "switch.wl000000000099_1_watering"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.wl000000000099_1_watering")
    assert state
    assert state.attributes.get(ATTR_WATERING_TIME) == 30

    # Set pause time
    await hass.services.async_call(
        WILIGHT_DOMAIN,
        SERVICE_SET_PAUSE_TIME,
        {ATTR_PAUSE_TIME: 18, ATTR_ENTITY_ID: "switch.wl000000000099_2_pause"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.wl000000000099_2_pause")
    assert state
    assert state.attributes.get(ATTR_PAUSE_TIME) == 18

    # Set trigger_1
    await hass.services.async_call(
        WILIGHT_DOMAIN,
        SERVICE_SET_TRIGGER,
        {
            ATTR_TRIGGER_INDEX: "1",
            ATTR_TRIGGER: "12715301",
            ATTR_ENTITY_ID: "switch.wl000000000099_1_watering",
        },
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.wl000000000099_1_watering")
    assert state
    assert state.attributes.get(ATTR_TRIGGER_1) == "12715301"

    # Set trigger_2
    await hass.services.async_call(
        WILIGHT_DOMAIN,
        SERVICE_SET_TRIGGER,
        {
            ATTR_TRIGGER_INDEX: "2",
            ATTR_TRIGGER: "12707301",
            ATTR_ENTITY_ID: "switch.wl000000000099_1_watering",
        },
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.wl000000000099_1_watering")
    assert state
    assert state.attributes.get(ATTR_TRIGGER_2) == "12707301"

    # Set trigger_3
    await hass.services.async_call(
        WILIGHT_DOMAIN,
        SERVICE_SET_TRIGGER,
        {
            ATTR_TRIGGER_INDEX: "3",
            ATTR_TRIGGER: "00015301",
            ATTR_ENTITY_ID: "switch.wl000000000099_1_watering",
        },
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.wl000000000099_1_watering")
    assert state
    assert state.attributes.get(ATTR_TRIGGER_3) == "00015301"

    # Set trigger_4
    await hass.services.async_call(
        WILIGHT_DOMAIN,
        SERVICE_SET_TRIGGER,
        {
            ATTR_TRIGGER_INDEX: "4",
            ATTR_TRIGGER: "00008300",
            ATTR_ENTITY_ID: "switch.wl000000000099_1_watering",
        },
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.wl000000000099_1_watering")
    assert state
    assert state.attributes.get(ATTR_TRIGGER_4) == "00008300"

    # Set watering time using WiLight Pause Switch to raise
    with pytest.raises(TypeError) as exc_info:
        await hass.services.async_call(
            WILIGHT_DOMAIN,
            SERVICE_SET_WATERING_TIME,
            {ATTR_WATERING_TIME: 30, ATTR_ENTITY_ID: "switch.wl000000000099_2_pause"},
            blocking=True,
        )

    assert str(exc_info.value) == "Entity is not a WiLight valve switch"
