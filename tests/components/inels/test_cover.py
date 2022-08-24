"""Inels cover platform testing."""
from homeassistant.core import HomeAssistant

from .conftest import setup_inels_test_integration

UNIQUE_ID = "2547858"

CONNECTED_TOPIC = f"inels/connected/7777888/03/{UNIQUE_ID}"
STATUS_TOPIC = f"inels/status/7777888/03/{UNIQUE_ID}"

CONNECTED_INELS_VALUE = b"on\n"
DISCONNECTED_INELS_VALUE = b"off\n"

COVER_CLOSED_VALUE = b"03\n00\n"
COVER_OPEN_VALUE = b"03\n01\n"


def set_mock_mqtt(mqtt, available):
    """Set mock mqtt communication."""
    mqtt.mock_messages[CONNECTED_TOPIC] = available
    mqtt.mock_messages[STATUS_TOPIC] = COVER_CLOSED_VALUE
    mqtt.mock_discovery_all[STATUS_TOPIC] = COVER_CLOSED_VALUE


def get_cover(hass: HomeAssistant, unique_id):
    """Return instance of the cover."""
    return hass.states.get(f"cover.{unique_id}")


async def test_cover_not_available(hass: HomeAssistant, mock_mqtt):
    """Test cover availability."""
    set_mock_mqtt(mock_mqtt, DISCONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    cover = get_cover(hass, UNIQUE_ID)
    assert cover is not None
    assert cover.state == "unavailable"


async def test_cover_available(hass: HomeAssistant, mock_mqtt):
    """Test cover availability."""
    set_mock_mqtt(mock_mqtt, CONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    cover = get_cover(hass, UNIQUE_ID)
    assert cover is not None
    assert cover.state == "closed"


async def test_cover_open(hass: HomeAssistant, mock_mqtt):
    """Test cover open state."""
    set_mock_mqtt(mock_mqtt, CONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    cover = get_cover(hass, UNIQUE_ID)
    assert cover is not None
    assert cover.state == "closed"

    mock_mqtt.mock_messages[STATUS_TOPIC] = COVER_OPEN_VALUE
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": f"cover.{UNIQUE_ID}"},
        blocking=True,
    )
    await hass.async_block_till_done()

    cover = get_cover(hass, UNIQUE_ID)
    assert cover is not None
    assert cover.state == "open"
