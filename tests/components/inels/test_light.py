"""Inels light platform testing."""
from homeassistant.core import HomeAssistant

from .conftest import setup_inels_test_integration

UNIQUE_ID = "48758455"

CONNECTED_TOPIC = f"inels/connected/7777888/05/{UNIQUE_ID}"
STATUS_TOPIC = f"inels/status/7777888/05/{UNIQUE_ID}"

CONNECTED_INELS_VALUE = b"on\n"
DISCONNECTED_INELS_VALUE = b"off\n"

TURN_OFF_AND_0_BRIGHTNESS = b"D8\nEF\n"
LIGHT_50_BRIGHTNESS = b"B1\nDF\n"
TURN_ON_AND_100_BRIGHTNESS = b"8A\nCF\n"


def set_mock_mqtt(mqtt, available):
    """Set mock mqtt communication."""
    mqtt.mock_messages[CONNECTED_TOPIC] = available
    mqtt.mock_messages[STATUS_TOPIC] = TURN_OFF_AND_0_BRIGHTNESS
    mqtt.mock_discovery_all[STATUS_TOPIC] = TURN_OFF_AND_0_BRIGHTNESS


def get_light(hass: HomeAssistant, unique_id):
    """Return instance of the light."""
    return hass.states.get(f"light.{unique_id}")


async def test_light(hass: HomeAssistant, mock_mqtt):
    """Test light added into the HA."""
    set_mock_mqtt(mock_mqtt, CONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    light = get_light(hass, UNIQUE_ID)
    assert light is not None
    assert light.state == "off"


async def test_light_not_available(hass: HomeAssistant, mock_mqtt):
    """Test light availability."""
    set_mock_mqtt(mock_mqtt, DISCONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    light = get_light(hass, UNIQUE_ID)
    assert light.state == "unavailable"


async def test_light_available(hass: HomeAssistant, mock_mqtt):
    """Test light availability."""
    set_mock_mqtt(mock_mqtt, CONNECTED_INELS_VALUE)
    mock_mqtt.mock_messages[STATUS_TOPIC] = TURN_ON_AND_100_BRIGHTNESS

    await setup_inels_test_integration(hass)

    light = get_light(hass, UNIQUE_ID)
    assert light.state == "on"


async def test_light_turn_on(hass: HomeAssistant, mock_mqtt):
    """Test light turn on."""
    set_mock_mqtt(mock_mqtt, CONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    light = get_light(hass, UNIQUE_ID)
    assert light.state == "off"

    mock_mqtt.mock_messages[STATUS_TOPIC] = TURN_ON_AND_100_BRIGHTNESS
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": f"light.{UNIQUE_ID}"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = get_light(hass, UNIQUE_ID)
    assert light.state == "on"


async def test_light_turn_off(hass: HomeAssistant, mock_mqtt):
    """Test light turn off."""
    set_mock_mqtt(mock_mqtt, CONNECTED_INELS_VALUE)
    mock_mqtt.mock_messages[STATUS_TOPIC] = LIGHT_50_BRIGHTNESS
    await setup_inels_test_integration(hass)

    light = get_light(hass, UNIQUE_ID)
    assert light.state == "on"
    # 50% of light brightness
    assert round(light.attributes["brightness"], 1) == 127.5

    mock_mqtt.mock_messages[STATUS_TOPIC] = TURN_OFF_AND_0_BRIGHTNESS
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": f"light.{UNIQUE_ID}"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = get_light(hass, UNIQUE_ID)
    assert light.state == "off"
