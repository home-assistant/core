"""Configuration for Ring tests."""
import pytest
import requests_mock

# from tests.common import load_fixture


@pytest.fixture(name="requests_mock")
def requests_mock_fixture():
    """Fixture to provide a requests mocker."""
    with requests_mock.mock() as mock:
        # Mocks the response for authenticating
        print("======= MRL Settup up mocks.")
        mock.post("https://api.carson.live/api/v1.4.1/auth/login/", status_code=400)

        yield mock
