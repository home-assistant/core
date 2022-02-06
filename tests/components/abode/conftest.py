"""Configuration for Abode tests."""
import abodepy.helpers.constants as CONST
import pytest

from tests.common import load_fixture
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
def requests_mock_fixture(requests_mock) -> None:
    """Fixture to provide a requests mocker."""
    # Mocks the login response for abodepy.
    requests_mock.post(CONST.LOGIN_URL, text=load_fixture("login.json", "abode"))
    # Mocks the logout response for abodepy.
    requests_mock.post(CONST.LOGOUT_URL, text=load_fixture("logout.json", "abode"))
    # Mocks the oauth claims response for abodepy.
    requests_mock.get(
        CONST.OAUTH_TOKEN_URL, text=load_fixture("oauth_claims.json", "abode")
    )
    # Mocks the panel response for abodepy.
    requests_mock.get(CONST.PANEL_URL, text=load_fixture("panel.json", "abode"))
    # Mocks the automations response for abodepy.
    requests_mock.get(
        CONST.AUTOMATION_URL, text=load_fixture("automation.json", "abode")
    )
    # Mocks the devices response for abodepy.
    requests_mock.get(CONST.DEVICES_URL, text=load_fixture("devices.json", "abode"))
