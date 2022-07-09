"""Configuration for fibaro tests."""
import pytest

from .const import TEST_URL

from tests.common import load_fixture


@pytest.fixture(autouse=True)
def requests_mock_fixture(requests_mock) -> None:
    """Fixture to provide a requests mocker."""
    # Mocks the login response for fibaro.
    requests_mock.get(
        TEST_URL + "loginStatus", text=load_fixture("login.json", "fibaro")
    )
    # Mocks the info response for fibaro.
    requests_mock.get(
        TEST_URL + "settings/info", text=load_fixture("info.json", "fibaro")
    )
    # Mocks the rooms response for fibaro.
    requests_mock.get(TEST_URL + "rooms", text=load_fixture("rooms.json", "fibaro"))
    # Mocks the scenes response for fibaro.
    requests_mock.get(TEST_URL + "scenes", text=load_fixture("scenes.json", "fibaro"))
    # Mocks the devices response for fibaro.
    requests_mock.get(TEST_URL + "devices", text=load_fixture("devices.json", "fibaro"))
