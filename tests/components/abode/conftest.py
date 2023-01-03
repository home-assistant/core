"""Configuration for Abode tests."""
from jaraco.abode.helpers import urls
import pytest

from tests.common import load_fixture
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
def requests_mock_fixture(requests_mock) -> None:
    """Fixture to provide a requests mocker."""
    # Mocks the login response for abodepy.
    requests_mock.post(urls.LOGIN, text=load_fixture("login.json", "abode"))
    # Mocks the logout response for abodepy.
    requests_mock.post(urls.LOGOUT, text=load_fixture("logout.json", "abode"))
    # Mocks the oauth claims response for abodepy.
    requests_mock.get(urls.OAUTH_TOKEN, text=load_fixture("oauth_claims.json", "abode"))
    # Mocks the panel response for abodepy.
    requests_mock.get(urls.PANEL, text=load_fixture("panel.json", "abode"))
    # Mocks the automations response for abodepy.
    requests_mock.get(urls.AUTOMATION, text=load_fixture("automation.json", "abode"))
    # Mocks the devices response for abodepy.
    requests_mock.get(urls.DEVICES, text=load_fixture("devices.json", "abode"))
