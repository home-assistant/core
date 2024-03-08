"""Configuration for 17Track tests."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.seventeentrack.sensor import (
    CONF_SHOW_ARCHIVED,
    CONF_SHOW_DELIVERED,
    DEFAULT_SCAN_INTERVAL,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed

VALID_CONFIG_MINIMAL = {
    "sensor": {
        "platform": "seventeentrack",
        CONF_USERNAME: "test",
        CONF_PASSWORD: "test",
    }
}

INVALID_CONFIG = {"sensor": {"platform": "seventeentrack", "boom": "test"}}

VALID_CONFIG_FULL = {
    "sensor": {
        "platform": "seventeentrack",
        CONF_USERNAME: "test",
        CONF_PASSWORD: "test",
        CONF_SHOW_ARCHIVED: True,
        CONF_SHOW_DELIVERED: True,
    }
}

VALID_CONFIG_FULL_NO_DELIVERED = {
    "sensor": {
        "platform": "seventeentrack",
        CONF_USERNAME: "test",
        CONF_PASSWORD: "test",
        CONF_SHOW_ARCHIVED: False,
        CONF_SHOW_DELIVERED: False,
    }
}

DEFAULT_SUMMARY = {
    "Not Found": 0,
    "In Transit": 0,
    "Expired": 0,
    "Ready to be Picked Up": 0,
    "Undelivered": 0,
    "Delivered": 0,
    "Returned": 0,
}

NEW_SUMMARY_DATA = {
    "Not Found": 1,
    "In Transit": 1,
    "Expired": 1,
    "Ready to be Picked Up": 1,
    "Undelivered": 1,
    "Delivered": 1,
    "Returned": 1,
}


@pytest.fixture
def mock_seventeentrack():
    """Build a fixture for the 17Track API."""
    mock_seventeentrack_api = AsyncMock()
    with (
        patch(
            "homeassistant.components.seventeentrack.sensor.SeventeenTrackClient",
            return_value=mock_seventeentrack_api,
        ) as mock_seventeentrack_api,
    ):
        mock_seventeentrack_api.return_value.profile.login.return_value = True
        mock_seventeentrack_api.return_value.profile.packages.return_value = []
        mock_seventeentrack_api.return_value.profile.summary.return_value = (
            DEFAULT_SUMMARY
        )
        yield mock_seventeentrack_api


async def _goto_future(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Move to future."""
    for _ in range(2):
        freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
