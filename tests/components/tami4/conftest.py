"""Common fixutres with default mocks as well as common test helper methods."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from Tami4EdgeAPI.device import Device
from Tami4EdgeAPI.device_metadata import DeviceMetadata
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
def mock_api(mock__get_devices_metadata, mock_get_device):
    """Fixture to mock all API calls."""


@pytest.fixture
def mock__get_devices_metadata(request: pytest.FixtureRequest) -> Generator[None]:
    """Fixture to mock _get_devices which makes a call to the API."""

    side_effect = getattr(request, "param", None)

    device_metadata = DeviceMetadata(
        id=1,
        name="Drink Water",
        connected=True,
        psn="psn",
        type="type",
        device_firmware="v1.1",
    )

    with patch(
        "Tami4EdgeAPI.Tami4EdgeAPI.Tami4EdgeAPI._get_devices_metadata",
        return_value=[device_metadata],
        side_effect=side_effect,
    ):
        yield


@pytest.fixture
def mock__get_devices_metadata_no_name(
    request: pytest.FixtureRequest,
) -> Generator[None]:
    """Fixture to mock _get_devices which makes a call to the API."""

    side_effect = getattr(request, "param", None)

    device_metadata = DeviceMetadata(
        id=1,
        name=None,
        connected=True,
        psn="psn",
        type="type",
        device_firmware="v1.1",
    )

    with patch(
        "Tami4EdgeAPI.Tami4EdgeAPI.Tami4EdgeAPI._get_devices_metadata",
        return_value=[device_metadata],
        side_effect=side_effect,
    ):
        yield


@pytest.fixture
def mock_get_device(
    request: pytest.FixtureRequest,
) -> Generator[None]:
    """Fixture to mock get_device which makes a call to the API."""

    side_effect = getattr(request, "param", None)

    water_quality = WaterQuality(
        uv=UV(
            upcoming_replacement=int(datetime.now().timestamp()),
            installed=True,
        ),
        filter=Filter(
            upcoming_replacement=int(datetime.now().timestamp()),
            milli_litters_passed=1000,
            installed=True,
        ),
    )

    device_metadata = DeviceMetadata(
        id=1,
        name="Drink Water",
        connected=True,
        psn="psn",
        type="type",
        device_firmware="v1.1",
    )

    device = Device(
        water_quality=water_quality, device_metadata=device_metadata, drinks=[]
    )

    with patch(
        "Tami4EdgeAPI.Tami4EdgeAPI.Tami4EdgeAPI.get_device",
        return_value=device,
        side_effect=side_effect,
    ):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""

    with patch(
        "homeassistant.components.tami4.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_request_otp(
    request: pytest.FixtureRequest,
) -> Generator[MagicMock]:
    """Mock request_otp."""

    side_effect = getattr(request, "param", None)

    with patch(
        "homeassistant.components.tami4.config_flow.Tami4EdgeAPI.request_otp",
        return_value=None,
        side_effect=side_effect,
    ) as mock_request_otp:
        yield mock_request_otp


@pytest.fixture
def mock_submit_otp(request: pytest.FixtureRequest) -> Generator[MagicMock]:
    """Mock submit_otp."""

    side_effect = getattr(request, "param", None)

    with patch(
        "homeassistant.components.tami4.config_flow.Tami4EdgeAPI.submit_otp",
        return_value="refresh_token",
        side_effect=side_effect,
    ) as mock_submit_otp:
        yield mock_submit_otp
