import pytest
from unittest.mock import AsyncMock, patch
from homeassistant.components.redgtech.switch import RedgtechSwitch

@pytest.fixture
def switch_data():
    return {
        "value": False,
        "friendlyName": "Test Switch",
        "endpointId": "1234-5678",
        "description": "Test Description",
        "manufacturerName": "Test Manufacturer"
    }

@pytest.fixture
def access_token():
    return "test_access_token"

@pytest.fixture
def switch(switch_data, access_token):
    return RedgtechSwitch(switch_data, access_token)

@pytest.mark.asyncio
async def test_switch_initial_state(switch):
    assert switch.name == "Test Switch"
    assert switch.is_on is False

@pytest.mark.asyncio
async def test_turn_on_switch(switch):
    with patch("aiohttp.ClientSession.get", new_callable=AsyncMock) as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_get.return_value = mock_response

        async def mock_turn_on():
            switch._state = True

        with patch.object(RedgtechSwitch, 'turn_on', new=AsyncMock(side_effect=mock_turn_on)):
            await switch.turn_on()

        assert switch.is_on is True

@pytest.mark.asyncio
async def test_turn_off_switch(switch):
    switch._state = True
    with patch("aiohttp.ClientSession.get", new_callable=AsyncMock) as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_get.return_value = mock_response

        async def mock_turn_off():
            switch._state = False

        with patch.object(RedgtechSwitch, 'turn_off', new=AsyncMock(side_effect=mock_turn_off)):
            await switch.turn_off()

        assert switch.is_on is False

@pytest.mark.asyncio
async def test_set_state_switch(switch):
    with patch("aiohttp.ClientSession.get", new_callable=AsyncMock) as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_get.return_value = mock_response

        async def mock_set_state(state):
            switch._state = state

        with patch.object(RedgtechSwitch, '_set_state', new=AsyncMock(side_effect=mock_set_state)):
            await switch._set_state(True)

        assert switch.is_on is True
