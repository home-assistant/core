"""Inels switch testing."""
from homeassistant.core import HomeAssistant

from .conftest import setup_inels_test_integration

SWITCH_UNIQUE_ID = "458745"

SWITCH_CONNECTED_TOPIC = f"inels/connected/7777888/02/{SWITCH_UNIQUE_ID}"
SWITCH_STATUS_TOPIC = f"inels/status/7777888/02/{SWITCH_UNIQUE_ID}"

SWITCH_ON_INELS_VALUE = b"02\n01\n"
SWITCH_OFF_INELS_VALUE = b"02\n00\n"
SWITCH_CONNECTED_INELS_VALUE = b"on\n"
SWITCH_DISCONNECTED_INELS_VALUE = b"off\n"


def set_mock_mqtt(mqtt, available):
    """Set mock mqtt communication."""
    mqtt.mock_messages[SWITCH_CONNECTED_TOPIC] = available
    mqtt.mock_messages[SWITCH_STATUS_TOPIC] = SWITCH_ON_INELS_VALUE
    mqtt.mock_discovery_all[SWITCH_STATUS_TOPIC] = SWITCH_ON_INELS_VALUE


def get_switch(hass: HomeAssistant, unique_id):
    """Return instance of the switch."""
    return hass.states.get(f"switch.{unique_id}")


async def test_switch(hass: HomeAssistant, mock_mqtt):
    """Test switch added into the HA."""
    set_mock_mqtt(mock_mqtt, SWITCH_CONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    switch = get_switch(hass, SWITCH_UNIQUE_ID)
    assert switch is not None


async def test_switch_not_available(hass: HomeAssistant, mock_mqtt):
    """Test switch availability."""
    set_mock_mqtt(mock_mqtt, SWITCH_DISCONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    switch = get_switch(hass, SWITCH_UNIQUE_ID)
    assert switch.state == "unavailable"


async def test_switch_available(hass: HomeAssistant, mock_mqtt):
    """Test switch availability."""
    set_mock_mqtt(mock_mqtt, SWITCH_CONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    switch = get_switch(hass, SWITCH_UNIQUE_ID)
    assert switch.state == "on"


async def test_switch_turn_off(hass: HomeAssistant, mock_mqtt):
    """Test switch turn off."""
    set_mock_mqtt(mock_mqtt, SWITCH_CONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    switch = get_switch(hass, SWITCH_UNIQUE_ID)
    assert switch.state == "on"

    mock_mqtt.mock_messages[SWITCH_STATUS_TOPIC] = SWITCH_OFF_INELS_VALUE
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": f"switch.{SWITCH_UNIQUE_ID}"},
        blocking=True,
    )
    await hass.async_block_till_done()

    switch = get_switch(hass, SWITCH_UNIQUE_ID)
    assert switch.state == "off"


async def test_switch_turn_on(hass: HomeAssistant, mock_mqtt):
    """Test switch turn off."""
    set_mock_mqtt(mock_mqtt, SWITCH_CONNECTED_INELS_VALUE)
    mock_mqtt.mock_messages[SWITCH_STATUS_TOPIC] = SWITCH_OFF_INELS_VALUE

    await setup_inels_test_integration(hass)

    switch = get_switch(hass, SWITCH_UNIQUE_ID)
    assert switch.state == "off"

    mock_mqtt.mock_messages[SWITCH_STATUS_TOPIC] = SWITCH_ON_INELS_VALUE
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": f"switch.{SWITCH_UNIQUE_ID}"},
        blocking=True,
    )
    await hass.async_block_till_done()

    switch = get_switch(hass, SWITCH_UNIQUE_ID)
    assert switch.state == "on"
