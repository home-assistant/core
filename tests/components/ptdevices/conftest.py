"""Common fixtures for the PTDevices tests."""

from collections.abc import AsyncGenerator, Generator
import json
from unittest.mock import AsyncMock, patch

from aioptdevices.interface import PTDevicesResponse
import pytest

from homeassistant.components.ptdevices.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_TOKEN

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_ptdevices_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ptdevices.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_ptdevices_level() -> PTDevicesResponse:
    """Mock a PTLevel device."""
    data = json.loads(load_fixture("ptdevices_level.json", integration=DOMAIN))
    return PTDevicesResponse(
        code=200,
        body=data,
    )


@pytest.fixture
def mock_ptdevices_level_missing_title() -> PTDevicesResponse:
    """Mock a malformed PTLevel response."""
    data = json.loads(load_fixture("ptdevices_level.json", integration=DOMAIN))
    data["C0FFEEC0FFEE"].pop("user_name")
    return PTDevicesResponse(
        code=200,
        body=data,
    )


@pytest.fixture
def mock_ptdevices_level_missing_device_id() -> PTDevicesResponse:
    """Mock a malformed PTLevel response."""
    data = json.loads(load_fixture("ptdevices_level.json", integration=DOMAIN))
    data["C0FFEEC0FFEE"].pop("id")
    return PTDevicesResponse(
        code=200,
        body=data,
    )


@pytest.fixture
async def mock_ptdevices_get_data(
    mock_ptdevices_level: PTDevicesResponse,
) -> AsyncGenerator[AsyncMock]:
    """Return a mocked ptdevices.request_status function."""

    with patch("aioptdevices.interface.Interface.get_data") as mock_request_status:
        mock_request_status.return_value = mock_ptdevices_level
        yield mock_request_status


@pytest.fixture
def mock_ptdevices_config_entry(
    request: pytest.FixtureRequest,
    mock_ptdevices_get_data: AsyncMock,
) -> MockConfigEntry:
    """Return a mocked ptdevice configuration entry."""
    entry_id = getattr(request, "param", None)

    return MockConfigEntry(
        entry_id=entry_id,
        version=1,
        domain=DOMAIN,
        title="Home",
        data={
            CONF_API_TOKEN: "test-api-token",
            # CONF_DEVICE_ID: "test-device-id",
        },
        unique_id="test-device-id",
        source=SOURCE_USER,
    )
