"""Fixtures for tests."""
import pytest

from tests.common import load_fixture


@pytest.fixture(autouse=True)
def requests_mock_fixture(requests_mock):
    """Fixture to provide a requests mocker."""
    requests_mock.get(
        "https://api.ecobee.com/1/thermostat",
        text=load_fixture("ecobee/ecobee-data.json"),
    )
    requests_mock.post(
        "https://api.ecobee.com/token",
        text=load_fixture("ecobee/ecobee-token.json"),
    )
