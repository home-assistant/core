"""Test fixtures for Prowl."""

from unittest.mock import patch

import pytest

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.prowl.const import DOMAIN as PROWL_DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

API_BASE_URL = "https://api.prowlapp.com/publicapi/"

TEST_API_KEY = "f00f" * 10
CONF_INPUT = {CONF_API_KEY: TEST_API_KEY, CONF_NAME: "TestProwl"}
INVALID_API_KEY_ERROR = {"base": "invalid_api_key"}
TIMEOUT_ERROR = {"base": "api_timeout"}
BAD_API_RESPONSE = {"base": "bad_api_response"}


@pytest.fixture
async def configure_prowl_through_yaml(hass: HomeAssistant):
    """Configure the notify domain with YAML for the Prowl platform."""
    await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {"platform": PROWL_DOMAIN, "api_key": TEST_API_KEY},
            ]
        },
    )
    await hass.async_block_till_done()


@pytest.fixture
def mock_pyprowl_success():
    """Mock a successful call to the PyProwl library."""
    with patch("pyprowl.Prowl") as MockProwl:
        mock_instance = MockProwl.return_value
        yield mock_instance


@pytest.fixture
def mock_pyprowl_fail():
    """Mock an unsuccessful call to the PyProwl library."""
    with patch("pyprowl.Prowl") as MockProwl:
        mock_instance = MockProwl.return_value
        mock_instance.verify_key.side_effect = Exception("500 Error")
        mock_instance.notify.side_effect = Exception("500 Error")
        yield mock_instance


@pytest.fixture
def mock_pyprowl_forbidden():
    """Mock an unsuccessful call to the PyProwl library."""
    with patch("pyprowl.Prowl") as MockProwl:
        mock_instance = MockProwl.return_value
        mock_instance.verify_key.side_effect = Exception("401 Unauthorized")
        mock_instance.notify.side_effect = Exception("401 Unauthorized")
        yield mock_instance


@pytest.fixture
def mock_pyprowl_timeout():
    """Mock an timeout to the PyProwl service."""
    with patch("pyprowl.Prowl") as MockProwl:
        mock_instance = MockProwl.return_value
        mock_instance.verify_key.side_effect = TimeoutError
        mock_instance.notify.side_effect = TimeoutError
        yield mock_instance


@pytest.fixture
def mock_pyprowl_syntax_error():
    """Mock a SyntaxError in the PyProwl service."""
    with patch("pyprowl.Prowl") as MockProwl:
        mock_instance = MockProwl.return_value
        mock_instance.verify_key.side_effect = SyntaxError
        mock_instance.notify.side_effect = SyntaxError
        yield mock_instance


@pytest.fixture
def mock_pyprowl_config_entry() -> MockConfigEntry:
    """Fixture to create a mocked ConfigEntry."""
    return MockConfigEntry(title="Mocked Prowl", domain=PROWL_DOMAIN, data=CONF_INPUT)
