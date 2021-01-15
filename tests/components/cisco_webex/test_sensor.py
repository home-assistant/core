"""Test the Cisco Webex config flow."""

from homeassistant.components.cisco_webex.sensor import WebexPresenceSensor

from tests.async_mock import patch
from tests.components.cisco_webex.mocks import MockWebexTeamsAPI

MOCK_API = MockWebexTeamsAPI(access_token="123")


async def test_update(hass):
    """Test update method."""

    WebexPresenceSensor(
        api=MOCK_API,
        email="test@123.com",
        name="Name").update()


async def test_update_people_not_found(hass):
    """Test update finds no people."""
    with patch(
            "tests.components.cisco_webex.mocks.MockPeopleAPI.list",
            return_value=[],
    ):
        WebexPresenceSensor(
            api=MOCK_API,
            email="test@123.com",
            name="Name").update()
