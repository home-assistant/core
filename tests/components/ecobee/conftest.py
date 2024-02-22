"""Fixtures for tests."""
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.ecobee import ECOBEE_API_KEY, ECOBEE_REFRESH_TOKEN

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


@pytest.fixture
def mock_ecobee():
    """Mock an Ecobee object."""
    ecobee = MagicMock()
    ecobee.request_pin.return_value = True
    ecobee.refresh_tokens.return_value = True

    ecobee.config = {ECOBEE_API_KEY: "mocked_key", ECOBEE_REFRESH_TOKEN: "mocked_token"}
    with patch("homeassistant.components.ecobee.Ecobee", return_value=ecobee):
        yield ecobee
