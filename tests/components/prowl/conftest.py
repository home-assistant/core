"""Test fixtures for Prowl."""

from unittest.mock import patch

import pytest

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.prowl.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

TEST_API_KEY = "f00f" * 10


@pytest.fixture
async def configure_prowl_through_yaml(hass: HomeAssistant, mock_pyprowl):
    """Configure the notify domain with YAML for the Prowl platform."""
    await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {
                    "name": DOMAIN,
                    "platform": DOMAIN,
                    "api_key": TEST_API_KEY,
                },
            ]
        },
    )
    await hass.async_block_till_done()


@pytest.fixture
def mock_pyprowl():
    """Mock the PyProwl library."""

    with patch("homeassistant.components.prowl.notify.pyprowl.Prowl") as MockProwl:
        mock_instance = MockProwl.return_value
        yield mock_instance
