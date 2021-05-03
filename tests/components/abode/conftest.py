"""Configuration for Abode tests."""
import abodepy.helpers.constants as CONST
import pytest

from tests.common import load_fixture
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
def requests_mock_fixture(requests_mock):
    """Fixture to provide a requests mocker."""
    # Mocks the login response for abodepy.
    requests_mock.post(CONST.LOGIN_URL, text=load_fixture("abode_login.json"))
    # Mocks the logout response for abodepy.
    requests_mock.post(CONST.LOGOUT_URL, text=load_fixture("abode_logout.json"))
    # Mocks the oauth claims response for abodepy.
    requests_mock.get(
        CONST.OAUTH_TOKEN_URL, text=load_fixture("abode_oauth_claims.json")
    )
    # Mocks the panel response for abodepy.
    requests_mock.get(CONST.PANEL_URL, text=load_fixture("abode_panel.json"))
    # Mocks the automations response for abodepy.
    requests_mock.get(CONST.AUTOMATION_URL, text=load_fixture("abode_automation.json"))
    # Mocks the devices response for abodepy.
    requests_mock.get(CONST.DEVICES_URL, text=load_fixture("abode_devices.json"))
