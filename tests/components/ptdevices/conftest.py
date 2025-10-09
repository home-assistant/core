"""Common fixtures for the PTDevices tests."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

from aioptdevices.interface import PTDevicesResponse
import pytest

from homeassistant.components.ptdevices.const import DOMAIN

from tests.common import load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ptdevices.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="ptdevices_level")
def mock_ptdevices_level():
    """Mock a PTLevel device."""
    data = json.loads(load_fixture("ptdevices_level.json", integration=DOMAIN))
    return PTDevicesResponse(
        code=200,
        body=data,
    )


@pytest.fixture(name="ptdevices_level_missing_title")
def mock_ptdevices_level_missing_title():
    """Mock a malformed PTLevel response."""
    data = json.loads(load_fixture("ptdevices_level.json", integration=DOMAIN))
    data.pop("title")
    return PTDevicesResponse(
        code=200,
        body=data,
    )


@pytest.fixture(name="ptdevices_level_missing_device_id")
def mock_ptdevices_level_missing_device_id():
    """Mock a malformed PTLevel response."""
    data = json.loads(load_fixture("ptdevices_level.json", integration=DOMAIN))
    data.pop("id")
    return PTDevicesResponse(
        code=200,
        body=data,
    )


# @pytest.fixture
# def mock_config_entry(
#     request: pytest.FixtureRequest,
#     mock_request_status: AsyncMock,
# ) -> MockConfigEntry:
#     """Mock setting up a config entry."""
#     entry_id = getattr(request, "param", None)
#     return MockConfigEntry(
#         entry_id=entry_id,
#         version=1,
#         domain=DOMAIN,
#         title="Home",
#         data={
#             CONF_API_TOKEN: "test-api-token",
#             CONF_DEVICE_ID: "test-device-id",
#         },
#         unique_id="test-device-id",
#         source=SOURCE_USER,
#     )
