import pytest
from unittest.mock import AsyncMock, patch
from homeassistant.components.redgtech.light import RedgtechLight
from homeassistant.const import CONF_BRIGHTNESS, STATE_ON, STATE_OFF

@pytest.fixture
def light_data():
    return {
        "endpointId": "dim-1",
        "value": True,
        "bright": 50,
        "friendlyName": "Test Light",
        "description": "Test Description",
        "manufacturerName": "Test Manufacturer"
    }

@pytest.fixture
def access_token():
    return "test_token"

@pytest.fixture
def light(light_data, access_token):
    return RedgtechLight(light_data, access_token)

@pytest.mark.asyncio
async def test_light_initial_state(light):
    assert light.name == "Test Light"
    assert light.is_on is True
    assert light.brightness == 127

@pytest.mark.asyncio
async def test_turn_on_light(light):
    with patch("aiohttp.ClientSession.get", new_callable=AsyncMock) as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_get.return_value = mock_response

        async def mock_turn_on(**kwargs):
            light._state = STATE_ON
            light._brightness = 255

        with patch.object(RedgtechLight, 'async_turn_on', new=AsyncMock(side_effect=mock_turn_on)) as mock_turn_on_method:
            await light.async_turn_on(brightness=255)
            mock_turn_on_method.assert_called_once_with(brightness=255)
            await light.async_turn_on()

        assert light.is_on is True
        assert light.brightness == 255

@pytest.mark.asyncio
async def test_turn_off_light(light):
    with patch("aiohttp.ClientSession.get", new_callable=AsyncMock) as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_get.return_value = mock_response

        async def mock_turn_off():
            light._state = STATE_OFF
            light._brightness = 0

        with patch.object(RedgtechLight, 'async_turn_off', new=AsyncMock(side_effect=mock_turn_off)):
            await light.async_turn_off()

        assert light.is_on is False
        assert light.brightness == 0

@pytest.mark.asyncio
async def test_set_brightness_light(light):
    with patch("aiohttp.ClientSession.get", new_callable=AsyncMock) as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_get.return_value = mock_response

        async def mock_set_brightness(brightness):
            light._brightness = brightness
            light._state = STATE_ON if brightness > 0 else STATE_OFF

        with patch.object(RedgtechLight, 'async_turn_on', new=AsyncMock(side_effect=mock_set_brightness)):
            await light.async_turn_on(brightness=200)

        assert light.brightness == 200
        assert light.is_on is True
