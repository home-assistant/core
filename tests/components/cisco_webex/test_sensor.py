"""Test the Cisco Webex config flow."""

from homeassistant.components.cisco_webex.sensor import WebexPresenceSensor

from tests.async_mock import patch
from tests.components.cisco_webex.mocks import MockWebexTeamsAPI

MOCK_API = MockWebexTeamsAPI(access_token="123")
SENSOR = WebexPresenceSensor(api=MOCK_API, email="test@123.com", name="Name")


async def test_update(hass):
    """Test update success."""

    sensor = WebexPresenceSensor(api=MOCK_API, email="test@123.com", name="Name")
    sensor.update()

    assert sensor._status == "active"
    assert sensor._avatar == "http://www.com/pic.png"
    assert sensor._name == "Webex Test user"
    assert sensor._user_id == "77777"


async def test_update_people_not_found(hass):
    """Test update finds no people."""
    with patch(
            "tests.components.cisco_webex.mocks.MockPeopleAPI.list",
            return_value=[],
    ):
        sensor = WebexPresenceSensor(api=MOCK_API, email="test@123.com", name="Name")
        sensor.update()

    assert sensor._status is None
    assert sensor._avatar is None
    assert sensor._name == "Name"
    assert sensor._user_id is None
