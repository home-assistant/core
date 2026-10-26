"""Tests for the Freebox covers (shutters)."""

from copy import deepcopy
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    CoverDeviceClass,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.components.freebox import SCAN_INTERVAL
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .common import setup_platform
from .const import DATA_HOME_SHUTTER_GET_VALUE


async def test_cover_attributes(hass: HomeAssistant, router: Mock) -> None:
    """Test Freebox shutter entity creation and initial attributes."""
    data_get_home_endpoint_value = deepcopy(DATA_HOME_SHUTTER_GET_VALUE)
    # Freebox OS: 0 = fully open -> HA position 100
    data_get_home_endpoint_value["value"] = 0
    router().home.get_home_endpoint_value.return_value = data_get_home_endpoint_value

    await setup_platform(hass, COVER_DOMAIN)

    shutter_1 = hass.states.get("cover.shutter_1")
    assert shutter_1 is not None
    assert shutter_1.state == CoverState.OPEN
    assert shutter_1.attributes[ATTR_CURRENT_POSITION] == 100
    assert shutter_1.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.SHUTTER
    assert shutter_1.attributes["supported_features"] == (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    shutter_2 = hass.states.get("cover.shutter_2")
    assert shutter_2 is not None
    assert shutter_2.state == CoverState.OPEN
    assert shutter_2.attributes[ATTR_CURRENT_POSITION] == 100


async def test_cover_commands_from_hass(hass: HomeAssistant, router: Mock) -> None:
    """Test Freebox shutter service calls (open, close, stop, set_position)."""
    data_get_home_endpoint_value = deepcopy(DATA_HOME_SHUTTER_GET_VALUE)
    data_get_home_endpoint_value["value"] = 0
    router().home.get_home_endpoint_value.return_value = data_get_home_endpoint_value

    await setup_platform(hass, COVER_DOMAIN)

    # 1. Close cover -> sends Freebox position 100 to slot 0 (position_set)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ["cover.shutter_1"]},
        blocking=True,
    )
    router().home.set_home_endpoint_value.assert_called_with(150, 0, {"value": 100})

    # 2. Open cover -> sends Freebox position 0 to slot 0 (position_set)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ["cover.shutter_1"]},
        blocking=True,
    )
    router().home.set_home_endpoint_value.assert_called_with(150, 0, {"value": 0})

    # 3. Stop cover -> calls slot 1 (stop)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: ["cover.shutter_1"]},
        blocking=True,
    )
    router().home.set_home_endpoint_value.assert_called_with(150, 1, {"value": None})

    # 4. Set cover position -> HA 70% open means Freebox 30
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ["cover.shutter_1"], ATTR_POSITION: 70},
        blocking=True,
    )
    router().home.set_home_endpoint_value.assert_called_with(150, 0, {"value": 30})

    # 5. Set cover position -> HA 0% open (fully closed) means Freebox 100
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ["cover.shutter_1"], ATTR_POSITION: 0},
        blocking=True,
    )
    router().home.set_home_endpoint_value.assert_called_with(150, 0, {"value": 100})


async def test_cover_state_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test Freebox shutter position and state updates from polling/timer."""
    data_get_home_endpoint_value = deepcopy(DATA_HOME_SHUTTER_GET_VALUE)
    # Freebox OS: 100 = closed -> HA position 0
    data_get_home_endpoint_value["value"] = 100
    router().home.get_home_endpoint_value.return_value = data_get_home_endpoint_value

    await setup_platform(hass, COVER_DOMAIN)

    shutter_1 = hass.states.get("cover.shutter_1")
    assert shutter_1 is not None
    assert shutter_1.state == CoverState.CLOSED
    assert shutter_1.attributes[ATTR_CURRENT_POSITION] == 0

    # Simulate shutter movement to 40% (Freebox) -> HA 60% open
    data_get_home_endpoint_value["value"] = 40
    router().home.get_home_endpoint_value.return_value = data_get_home_endpoint_value

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    shutter_1 = hass.states.get("cover.shutter_1")
    assert shutter_1 is not None
    assert shutter_1.state == CoverState.OPEN
    assert shutter_1.attributes[ATTR_CURRENT_POSITION] == 60


async def test_cover_unknown_state(hass: HomeAssistant, router: Mock) -> None:
    """Test Freebox shutter when position is None / undefined."""
    data_get_home_endpoint_value = deepcopy(DATA_HOME_SHUTTER_GET_VALUE)
    data_get_home_endpoint_value["value"] = None
    router().home.get_home_endpoint_value.return_value = data_get_home_endpoint_value

    await setup_platform(hass, COVER_DOMAIN)

    shutter_1 = hass.states.get("cover.shutter_1")
    assert shutter_1 is not None
    assert shutter_1.state == STATE_UNKNOWN
    assert shutter_1.attributes.get(ATTR_CURRENT_POSITION) is None
