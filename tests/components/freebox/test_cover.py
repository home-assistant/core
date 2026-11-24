"""Tests for the Freebox covers (shutters)."""

import base64
from copy import deepcopy
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
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
from .const import DATA_HOME_GET_NODES


async def test_cover_attributes(hass: HomeAssistant, router: Mock) -> None:
    """Test Freebox shutter entity creation and initial attributes."""
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

    rts_shutter = hass.states.get("cover.rts_shutter")
    assert rts_shutter is not None
    assert rts_shutter.state == CoverState.OPEN
    assert rts_shutter.attributes.get(ATTR_CURRENT_POSITION) is None
    assert rts_shutter.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.SHUTTER
    assert rts_shutter.attributes["supported_features"] == (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )


async def test_cover_commands_from_hass(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test Freebox shutter service calls (open, close, stop, set_position)."""
    await setup_platform(hass, COVER_DOMAIN)

    # 1. Close cover -> sends Freebox position 100 to slot 0 (position_set)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ["cover.shutter_1"]},
        blocking=True,
    )
    router().home.set_home_endpoint_value.assert_called_with(150, 0, {"value": 100})
    # The position is unknown until the device reports the move
    assert hass.states.get("cover.shutter_1").state == STATE_UNKNOWN

    # 2. Open cover -> sends Freebox position 0 to slot 0 (position_set)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ["cover.shutter_1"]},
        blocking=True,
    )
    router().home.set_home_endpoint_value.assert_called_with(150, 0, {"value": 0})
    assert hass.states.get("cover.shutter_1").state == STATE_UNKNOWN

    # 3. Stop cover -> calls slot 1 (stop)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: ["cover.shutter_1"]},
        blocking=True,
    )
    router().home.set_home_endpoint_value.assert_called_with(150, 1, {"value": None})
    assert hass.states.get("cover.shutter_1").state == STATE_UNKNOWN

    # 4. Set cover position -> HA 70% open means Freebox 30
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ["cover.shutter_1"], ATTR_POSITION: 70},
        blocking=True,
    )
    router().home.set_home_endpoint_value.assert_called_with(150, 0, {"value": 30})
    assert hass.states.get("cover.shutter_1").state == STATE_UNKNOWN

    # 5. The device reports the reached position
    data_home_nodes = deepcopy(DATA_HOME_GET_NODES)
    for node in data_home_nodes:
        if node["id"] == 150:
            for ep in node["show_endpoints"]:
                if ep["name"] == "position_set":
                    ep["value"] = 30  # Freebox 30 -> HA 70
    router().home.get_home_nodes.return_value = data_home_nodes

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    shutter_1 = hass.states.get("cover.shutter_1")
    assert shutter_1.state == CoverState.OPEN
    assert shutter_1.attributes[ATTR_CURRENT_POSITION] == 70


async def test_basic_shutter_commands_from_hass(
    hass: HomeAssistant, router: Mock
) -> None:
    """Test Freebox RTS basic shutter service calls (open, close, stop)."""
    await setup_platform(hass, COVER_DOMAIN)

    # 1. Close basic cover -> calls down slot (id 2)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ["cover.rts_shutter"]},
        blocking=True,
    )
    router().home.set_home_endpoint_value.assert_called_with(152, 2, {"value": None})
    assert hass.states.get("cover.rts_shutter").state == CoverState.CLOSED

    # 2. Open basic cover -> calls up slot (id 0)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ["cover.rts_shutter"]},
        blocking=True,
    )
    router().home.set_home_endpoint_value.assert_called_with(152, 0, {"value": None})
    assert hass.states.get("cover.rts_shutter").state == CoverState.OPEN

    # 3. Stop basic cover -> calls stop slot (id 1)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: ["cover.rts_shutter"]},
        blocking=True,
    )
    router().home.set_home_endpoint_value.assert_called_with(152, 1, {"value": None})


async def test_cover_state_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test Freebox shutter position and state updates from router."""
    await setup_platform(hass, COVER_DOMAIN)

    shutter_1 = hass.states.get("cover.shutter_1")
    assert shutter_1 is not None
    assert shutter_1.state == CoverState.OPEN
    assert shutter_1.attributes[ATTR_CURRENT_POSITION] == 100

    # Simulate shutter movement: router gets updated nodes
    data_home_nodes = deepcopy(DATA_HOME_GET_NODES)
    for node in data_home_nodes:
        if node["id"] == 150:
            for ep in node["show_endpoints"]:
                if ep["name"] == "position_set":
                    ep["value"] = 40  # Freebox 40 -> HA 60
    router().home.get_home_nodes.return_value = data_home_nodes

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    shutter_1 = hass.states.get("cover.shutter_1")
    assert shutter_1 is not None
    assert shutter_1.state == CoverState.OPEN
    assert shutter_1.attributes[ATTR_CURRENT_POSITION] == 60


async def test_cover_unknown_state(hass: HomeAssistant, router: Mock) -> None:
    """Test Freebox shutter when position is None / undefined."""
    data_home_nodes = deepcopy(DATA_HOME_GET_NODES)
    for node in data_home_nodes:
        if node["id"] == 150:
            for ep in node["show_endpoints"]:
                if ep["name"] == "position_set":
                    ep["value"] = None
    router().home.get_home_nodes.return_value = data_home_nodes

    await setup_platform(hass, COVER_DOMAIN)

    shutter_1 = hass.states.get("cover.shutter_1")
    assert shutter_1 is not None
    assert shutter_1.state == STATE_UNKNOWN
    assert shutter_1.attributes.get(ATTR_CURRENT_POSITION) is None


def _make_state_frame(flag: int) -> str:
    """Return a base64-encoded 59-byte state frame with the given flag at byte 50."""
    frame = bytearray(59)
    frame[50] = flag
    return base64.b64encode(bytes(frame)).decode()


@pytest.mark.parametrize(
    ("flag", "position_set", "expected_position", "expected_state"),
    [
        pytest.param(0x00, 42, 100, CoverState.OPEN, id="fully-open"),
        pytest.param(0xC8, 42, 0, CoverState.CLOSED, id="fully-closed"),
        pytest.param(0x01, 40, 60, CoverState.OPEN, id="moving"),
        pytest.param(0x01, 0, 50, CoverState.OPEN, id="fallback"),
    ],
)
async def test_cover_encoded_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    router: Mock,
    flag: int,
    position_set: int,
    expected_position: int,
    expected_state: CoverState,
) -> None:
    """Test Freebox shutter position decoding from the encoded state frame."""
    await setup_platform(hass, COVER_DOMAIN)

    data_home_nodes = deepcopy(DATA_HOME_GET_NODES)
    for node in data_home_nodes:
        if node["id"] == 150:
            for ep in node["show_endpoints"]:
                if ep["name"] == "position_set":
                    ep["value"] = position_set
                elif ep["name"] == "state":
                    ep["value"] = _make_state_frame(flag)
    router().home.get_home_nodes.return_value = data_home_nodes

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    shutter_1 = hass.states.get("cover.shutter_1")
    assert shutter_1.attributes[ATTR_CURRENT_POSITION] == expected_position
    assert shutter_1.state == expected_state
