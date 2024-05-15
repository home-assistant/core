"""Sanix tests configuration."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from sanix import (
    ATTR_API_BATTERY,
    ATTR_API_DEVICE_NO,
    ATTR_API_DISTANCE,
    ATTR_API_FILL_PERC,
    ATTR_API_SERVICE_DATE,
    ATTR_API_SSID,
    ATTR_API_STATUS,
    ATTR_API_TIME,
)
from sanix.models import Measurement

from homeassistant.components.sanix.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.const import CONF_TOKEN

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_sanix():
    """Build a fixture for the Sanix API that connects successfully and returns measurements."""
    fixture = load_json_object_fixture("get_measurements.json", DOMAIN)
    with (
        patch(
            "homeassistant.components.sanix.config_flow.Sanix",
            autospec=True,
        ) as mock_sanix_api,
        patch(
            "homeassistant.components.sanix.Sanix",
            new=mock_sanix_api,
        ),
    ):
        mock_sanix_api.return_value.fetch_data.return_value = Measurement(
            battery=fixture[ATTR_API_BATTERY],
            device_no=fixture[ATTR_API_DEVICE_NO],
            distance=fixture[ATTR_API_DISTANCE],
            fill_perc=fixture[ATTR_API_FILL_PERC],
            service_date=datetime.strptime(
                fixture[ATTR_API_SERVICE_DATE], "%d.%m.%Y"
            ).date(),
            ssid=fixture[ATTR_API_SSID],
            status=fixture[ATTR_API_STATUS],
            time=datetime.strptime(fixture[ATTR_API_TIME], "%d.%m.%Y %H:%M:%S").replace(
                tzinfo=ZoneInfo("Europe/Warsaw")
            ),
        )
        yield mock_sanix_api


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Sanix",
        unique_id="1810088",
        data={CONF_SERIAL_NUMBER: "1234", CONF_TOKEN: "abcd"},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sanix.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
