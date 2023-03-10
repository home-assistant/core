"""iNELS cover platform testing."""
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from .conftest import setup_inels_test_integration

MAC_ADDRESS = "001122334455"
DEV_TYPE = "21"
UNIQUE_ID = "000021"

CONNECTED_TOPIC = f"inels/connected/{MAC_ADDRESS}/{DEV_TYPE}/{UNIQUE_ID}"
STATUS_TOPIC = f"inels/status/{MAC_ADDRESS}/{DEV_TYPE}/{UNIQUE_ID}"
BASE_TOPIC = f"{MAC_ADDRESS}/{DEV_TYPE}/{UNIQUE_ID}"

CONNECTED_INELS_VALUE = b"on\n"
DISCONNECTED_INELS_VALUE = b"off\n"

COVER_OPEN_VALUE = b"03\n00\n00\n"
COVER_CLOSED_VALUE = b"03\n02\n64\n"
COVER_OPEN_HALF_VALUE = b"03\n00\n32\n"


def set_mock_mqtt(mqtt, available):
    """Set mock mqtt communication."""
    mqtt.mock_messages[CONNECTED_TOPIC] = available
    mqtt.mock_messages[STATUS_TOPIC] = COVER_CLOSED_VALUE
    mqtt.mock_discovery_all[BASE_TOPIC] = COVER_CLOSED_VALUE


def get_cover(hass: HomeAssistant, unique_id):
    """Return instance of the cover."""
    return hass.states.get(f"cover.{MAC_ADDRESS}_{unique_id}_shutters_with_pos")


async def test_cover_not_available(hass: HomeAssistant, mock_mqtt) -> None:
    """Test cover availability."""
    set_mock_mqtt(mock_mqtt, DISCONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    cover = get_cover(hass, UNIQUE_ID)
    assert cover is not None
    assert cover.state == "unavailable"


async def test_cover_available(hass: HomeAssistant, mock_mqtt) -> None:
    """Test cover availability."""
    set_mock_mqtt(mock_mqtt, CONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    cover = get_cover(hass, UNIQUE_ID)
    assert cover is not None
    assert cover.state == "closed"


async def test_cover_open(hass: HomeAssistant, mock_mqtt) -> None:
    """Test cover open state."""
    set_mock_mqtt(mock_mqtt, CONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    cover = get_cover(hass, UNIQUE_ID)
    assert cover is not None
    assert cover.state == "closed"

    mock_mqtt.mock_messages[STATUS_TOPIC] = COVER_OPEN_VALUE
    with patch("inelsmqtt.devices.Device.set_ha_value") as mock_open:
        await hass.services.async_call(
            "cover",
            "open_cover",
            {"entity_id": f"cover.{MAC_ADDRESS}_{UNIQUE_ID}_shutters_with_pos"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_open.assert_called_once()


async def test_set_position(hass: HomeAssistant, mock_mqtt) -> None:
    """Test set position method."""
    set_mock_mqtt(mock_mqtt, CONNECTED_INELS_VALUE)
    mock_mqtt.mock_messages[STATUS_TOPIC] = COVER_OPEN_HALF_VALUE
    await setup_inels_test_integration(hass)

    cover = get_cover(hass, UNIQUE_ID)
    assert cover is not None
    assert cover.state == "open"
    assert round(cover.attributes["current_position"], 0) == 50.0

    mock_mqtt.mock_messages[STATUS_TOPIC] = COVER_OPEN_VALUE
    with patch("inelsmqtt.devices.Device.set_ha_value") as mock_open:
        await hass.services.async_call(
            "cover",
            "set_cover_position",
            {
                "entity_id": f"cover.{MAC_ADDRESS}_{UNIQUE_ID}_shutters_with_pos",
                "position": 50.0,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_open.assert_called_once()
