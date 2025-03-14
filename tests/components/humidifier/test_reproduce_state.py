"""The tests for reproduction of state."""

import pytest

from homeassistant.components.humidifier.const import (
    ATTR_HUMIDITY,
    DOMAIN,
    MODE_AWAY,
    MODE_ECO,
    MODE_NORMAL,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
)
from homeassistant.components.humidifier.reproduce_state import async_reproduce_states
from homeassistant.const import (
    ATTR_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service

ENTITY_1 = "humidifier.test1"
ENTITY_2 = "humidifier.test2"


async def test_reproducing_on_off_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing humidifier states."""
    hass.states.async_set(ENTITY_1, "off", {ATTR_MODE: MODE_NORMAL, ATTR_HUMIDITY: 45})
    hass.states.async_set(ENTITY_2, "on", {ATTR_MODE: MODE_NORMAL, ATTR_HUMIDITY: 45})

    turn_on_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    turn_off_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)
    mode_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_MODE)
    humidity_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_HUMIDITY)

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State(ENTITY_1, "off", {ATTR_MODE: MODE_NORMAL, ATTR_HUMIDITY: 45}),
            State(ENTITY_2, "on", {ATTR_MODE: MODE_NORMAL, ATTR_HUMIDITY: 45}),
        ],
    )

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(mode_calls) == 0
    assert len(humidity_calls) == 0

    # Test invalid state is handled
    await async_reproduce_state(hass, [State(ENTITY_1, "not_supported")])

    assert "not_supported" in caplog.text
    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(mode_calls) == 0
    assert len(humidity_calls) == 0

    # Make sure correct services are called
    await async_reproduce_state(
        hass,
        [
            State(ENTITY_2, "off"),
            State(ENTITY_1, "on", {}),
            # Should not raise
            State("humidifier.non_existing", "on"),
        ],
    )

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "humidifier"
    assert turn_on_calls[0].data == {"entity_id": ENTITY_1}

    assert len(turn_off_calls) == 1
    assert turn_off_calls[0].domain == "humidifier"
    assert turn_off_calls[0].data == {"entity_id": ENTITY_2}

    # Make sure we didn't call services for missing attributes
    assert len(mode_calls) == 0
    assert len(humidity_calls) == 0


async def test_multiple_attrs(hass: HomeAssistant) -> None:
    """Test turn on with multiple attributes."""
    hass.states.async_set(ENTITY_1, STATE_OFF, {})

    turn_on_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    turn_off_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)
    mode_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_MODE)
    humidity_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_HUMIDITY)

    await async_reproduce_states(
        hass, [State(ENTITY_1, STATE_ON, {ATTR_MODE: MODE_NORMAL, ATTR_HUMIDITY: 45})]
    )

    await hass.async_block_till_done()

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].data == {"entity_id": ENTITY_1}
    assert len(turn_off_calls) == 0
    assert len(mode_calls) == 1
    assert mode_calls[0].data == {"entity_id": ENTITY_1, "mode": "normal"}
    assert len(humidity_calls) == 1
    assert humidity_calls[0].data == {"entity_id": ENTITY_1, "humidity": 45}


async def test_turn_off_multiple_attrs(hass: HomeAssistant) -> None:
    """Test set mode and humidity for off state."""
    hass.states.async_set(ENTITY_1, STATE_ON, {})

    turn_on_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    turn_off_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)
    mode_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_MODE)
    humidity_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_HUMIDITY)

    await async_reproduce_states(
        hass, [State(ENTITY_1, STATE_OFF, {ATTR_MODE: MODE_NORMAL, ATTR_HUMIDITY: 45})]
    )

    await hass.async_block_till_done()

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 1
    assert turn_off_calls[0].data == {"entity_id": ENTITY_1}
    assert len(mode_calls) == 0
    assert len(humidity_calls) == 0


async def test_multiple_modes(hass: HomeAssistant) -> None:
    """Test that multiple states gets calls."""
    hass.states.async_set(ENTITY_1, STATE_OFF, {})
    hass.states.async_set(ENTITY_2, STATE_OFF, {})

    turn_on_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    turn_off_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)
    mode_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_MODE)
    humidity_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_HUMIDITY)

    await async_reproduce_states(
        hass,
        [
            State(ENTITY_1, STATE_ON, {ATTR_MODE: MODE_ECO, ATTR_HUMIDITY: 40}),
            State(ENTITY_2, STATE_ON, {ATTR_MODE: MODE_NORMAL, ATTR_HUMIDITY: 50}),
        ],
    )

    await hass.async_block_till_done()

    assert len(turn_on_calls) == 2
    assert len(turn_off_calls) == 0
    assert len(mode_calls) == 2
    # order is not guaranteed
    assert any(
        call.data == {"entity_id": ENTITY_1, "mode": MODE_ECO} for call in mode_calls
    )
    assert any(
        call.data == {"entity_id": ENTITY_2, "mode": MODE_NORMAL} for call in mode_calls
    )
    assert len(humidity_calls) == 2
    # order is not guaranteed
    assert any(
        call.data == {"entity_id": ENTITY_1, "humidity": 40} for call in humidity_calls
    )
    assert any(
        call.data == {"entity_id": ENTITY_2, "humidity": 50} for call in humidity_calls
    )


async def test_state_with_none(hass: HomeAssistant) -> None:
    """Test that none is not a humidifier state."""
    hass.states.async_set(ENTITY_1, STATE_OFF, {})

    turn_on_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    turn_off_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)
    mode_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_MODE)
    humidity_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_HUMIDITY)

    await async_reproduce_states(hass, [State(ENTITY_1, None)])

    await hass.async_block_till_done()

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(mode_calls) == 0
    assert len(humidity_calls) == 0


async def test_state_with_context(hass: HomeAssistant) -> None:
    """Test that context is forwarded."""
    hass.states.async_set(ENTITY_1, STATE_OFF, {})

    turn_on_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    turn_off_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)
    mode_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_MODE)
    humidity_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_HUMIDITY)

    context = Context()

    await async_reproduce_states(
        hass,
        [State(ENTITY_1, STATE_ON, {ATTR_MODE: MODE_AWAY, ATTR_HUMIDITY: 45})],
        context=context,
    )

    await hass.async_block_till_done()

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].data == {"entity_id": ENTITY_1}
    assert turn_on_calls[0].context == context
    assert len(turn_off_calls) == 0
    assert len(mode_calls) == 1
    assert mode_calls[0].data == {"entity_id": ENTITY_1, "mode": "away"}
    assert mode_calls[0].context == context
    assert len(humidity_calls) == 1
    assert humidity_calls[0].data == {"entity_id": ENTITY_1, "humidity": 45}
    assert humidity_calls[0].context == context


@pytest.mark.parametrize(
    ("service", "attribute"),
    [(SERVICE_SET_MODE, ATTR_MODE), (SERVICE_SET_HUMIDITY, ATTR_HUMIDITY)],
)
async def test_attribute(hass: HomeAssistant, service, attribute) -> None:
    """Test that service call is made for each attribute."""
    hass.states.async_set(ENTITY_1, STATE_ON, {})

    turn_on_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    turn_off_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)
    calls_1 = async_mock_service(hass, DOMAIN, service)

    value = "dummy"

    await async_reproduce_states(hass, [State(ENTITY_1, STATE_ON, {attribute: value})])

    await hass.async_block_till_done()

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(calls_1) == 1
    assert calls_1[0].data == {"entity_id": ENTITY_1, attribute: value}
