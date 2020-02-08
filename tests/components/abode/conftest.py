"""Configuration for Abode tests."""
import abodepy.helpers.constants as CONST
import pytest
import requests_mock

from tests.common import load_fixture


@pytest.fixture(name="requests_mock")
def requests_mock_fixture():
    """Fixture to provide a requests mocker."""
    with requests_mock.mock() as mock:
        # Mocks the login response for abodepy.
        mock.post(CONST.LOGIN_URL, text=load_fixture("abode_login.json"))
        # Mocks the logout response for abodepy.
        mock.post(CONST.LOGOUT_URL, text=load_fixture("abode_logout.json"))
        # Mocks the oauth claims response for abodepy.
        mock.get(CONST.OAUTH_TOKEN_URL, text=load_fixture("abode_oauth_claims.json"))
        # Mocks the panel response for abodepy.
        mock.get(CONST.PANEL_URL, text=load_fixture("abode_panel.json"))
        # Mocks the automations response for abodepy.
        mock.get(CONST.AUTOMATION_URL, text=load_fixture("abode_automation.json"))
        # Mocks the devices response for abodepy.
        mock.get(CONST.DEVICES_URL, text=load_fixture("abode_devices.json"))

        yield mock
