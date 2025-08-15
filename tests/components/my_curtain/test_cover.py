                                                                                                                                                                                                                                                """Test Alexa cover capabilities."""

import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant

from .test_common import (
    assert_request_calls_service,
    assert_request_fails,
    get_default_config,
    get_new_request,
    reported_properties,
)


async def test_discovery_cover(hass: HomeAssistant) -> None:
    """Test discovery for a cover entity."""
    request = get_new_request("Alexa.Discovery", "Discover")
    #  setup test cover device
    hass.states.async_set(
        "cover.test",
        STATE_OPEN,
        {
            "friendly_name": "Test Curtain",
            ATTR_CURRENT_POSITION: 80,
            "supported_features": 15,  # 支持打开、关闭、停止、设置位置
        },
    )
    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)
    assert "event" in msg
    msg = msg["event"]
    assert len(msg["payload"]["endpoints"]) == 1
    endpoint = msg["payload"]["endpoints"][0]
    assert endpoint["endpointId"] == "cover#test"
    interfaces = {capability["interface"] for capability in endpoint["capabilities"]}
    assert "Alexa.PowerController" in interfaces
    assert "Alexa.RangeController" in interfaces


async def test_api_open_cover(hass: HomeAssistant) -> None:
    """Test opening a cover."""
    call, _ = await assert_request_calls_service(
        "Alexa.PowerController",
        "TurnOn",
        "cover#test",
        "cover.open_cover",
        hass,
    )
    assert call.data["entity_id"] == "cover.test"


async def test_api_close_cover(hass: HomeAssistant) -> None:
    """Test closing a cover."""
    call, _ = await assert_request_calls_service(
        "Alexa.PowerController",
        "TurnOff",
        "cover#test",
        "cover.close_cover",
        hass,
    )
    assert call.data["entity_id"] == "cover.test"


async def test_api_stop_cover(hass: HomeAssistant) -> None:
    """Test stopping a cover."""
    call, _ = await assert_request_calls_service(
        "Alexa.RangeController",
        "AdjustRangeValue",
        "cover#test",
        "cover.stop_cover",
        hass,
        payload={"rangeValueDelta": 0, "unit": "percentage"},
        instance="Cover.Position",
    )
    assert call.data["entity_id"] == "cover.test"


@pytest.mark.parametrize("position", [0, 50, 100])
async def test_api_set_cover_position(hass: HomeAssistant, position: int) -> None:
    """Test setting cover position."""
    call, _ = await assert_request_calls_service(
        "Alexa.RangeController",
        "SetRangeValue",
        "cover#test",
        "cover.set_cover_position",
        hass,
        payload={"rangeValue": position, "unit": "percentage"},
        instance="Cover.Position",
    )
    assert call.data["entity_id"] == "cover.test"
    assert call.data[ATTR_POSITION] == position


async def test_api_set_invalid_position(hass: HomeAssistant) -> None:
    """Test setting invalid cover position (out of 0-100 range)."""
    await assert_request_fails(
        "Alexa.RangeController",
        "SetRangeValue",
        "cover#test",
        "cover.set_cover_position",
        hass,
        payload={"rangeValue": 150, "unit": "percentage"},
        instance="Cover.Position",
    )


async def test_reported_properties(hass: HomeAssistant) -> None:
    """Test reported properties for cover."""
    hass.states.async_set(
        "cover.test",
        STATE_OPEN,
        {
            ATTR_CURRENT_POSITION: 30,
            "friendly_name": "Test Curtain",
        },
    )
    props = await reported_properties(hass, "cover#test")
    props.assert_equal("Alexa.RangeController", "rangeValue", 30)
    props.assert_equal("Alexa.PowerController", "powerState", "ON")

    hass.states.async_set(
        "cover.test",
        STATE_CLOSED,
        {
            ATTR_CURRENT_POSITION: 0,
            "friendly_name": "Test Curtain",
        },
    )
    props = await reported_properties(hass, "cover#test")
    props.assert_equal("Alexa.RangeController", "rangeValue", 0)
    props.assert_equal("Alexa.PowerController", "powerState", "OFF")


async def test_cover_in_transition(hass: HomeAssistant) -> None:
    """Test cover in opening/closing state reports correct properties."""
    hass.states.async_set(
        "cover.test",
        STATE_OPENING,
        {
            ATTR_CURRENT_POSITION: 50,
            "friendly_name": "Test Curtain",
        },
    )
    props = await reported_properties(hass, "cover#test")
    props.assert_equal("Alexa.RangeController", "rangeValue", 50)
    props.assert_equal("Alexa.PowerController", "powerState", "ON")

    hass.states.async_set(
        "cover.test",
        STATE_CLOSING,
        {
            ATTR_CURRENT_POSITION: 50,
            "friendly_name": "Test Curtain",
        },
    )
    props = await reported_properties(hass, "cover#test")
    props.assert_equal("Alexa.RangeController", "rangeValue", 50)
    props.assert_equal("Alexa.PowerController", "powerState", "ON")