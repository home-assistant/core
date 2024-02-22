"""Common fixutres with default mocks as well as common test helper methods."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from Tami4EdgeAPI.device import Device
from Tami4EdgeAPI.water_quality import UV, Filter, WaterQuality

from homeassistant.components.tami4.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def create_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create an entry in hass."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Device name",
        data={CONF_REFRESH_TOKEN: "refresh_token"},
    )

    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture
def mock_api(mock__get_devices, mock_get_water_quality):
    """Fixture to mock all API calls."""


@pytest.fixture
def mock__get_devices(request):
    """Fixture to mock _get_devices which makes a call to the API."""

    side_effect = getattr(request, "param", None)

    device = Device(
        id=1,
        name="Drink Water",
        connected=True,
        psn="psn",
        type="type",
        device_firmware="v1.1",
    )

    with patch(
        "Tami4EdgeAPI.Tami4EdgeAPI.Tami4EdgeAPI._get_devices",
        return_value=[device],
        side_effect=side_effect,
    ):
        yield


@pytest.fixture
def mock_get_water_quality(request):
    """Fixture to mock get_water_quality which makes a call to the API."""

    side_effect = getattr(request, "param", None)

    water_quality = WaterQuality(
        uv=UV(
            last_replacement=int(datetime.now().timestamp()),
            upcoming_replacement=int(datetime.now().timestamp()),
            status="on",
        ),
        filter=Filter(
            last_replacement=int(datetime.now().timestamp()),
            upcoming_replacement=int(datetime.now().timestamp()),
            status="on",
            milli_litters_passed=1000,
        ),
    )

    with patch(
        "Tami4EdgeAPI.Tami4EdgeAPI.Tami4EdgeAPI.get_water_quality",
        return_value=water_quality,
        side_effect=side_effect,
    ):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""

    with patch(
        "homeassistant.components.tami4.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_request_otp(request):
    """Mock request_otp."""

    side_effect = getattr(request, "param", None)

    with patch(
        "homeassistant.components.tami4.config_flow.Tami4EdgeAPI.request_otp",
        return_value=None,
        side_effect=side_effect,
    ) as mock_request_otp:
        yield mock_request_otp


@pytest.fixture
def mock_submit_otp(request):
    """Mock submit_otp."""

    side_effect = getattr(request, "param", None)

    with patch(
        "homeassistant.components.tami4.config_flow.Tami4EdgeAPI.submit_otp",
        return_value="refresh_token",
        side_effect=side_effect,
    ) as mock_submit_otp:
        yield mock_submit_otp
