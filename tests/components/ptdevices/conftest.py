"""Common fixtures for the PTDevices tests."""

from collections.abc import Generator
from typing import cast
from unittest.mock import AsyncMock, patch

from aioptdevices.interface import PTDevicesResponse, PTDevicesResponseData
import pytest

from homeassistant.components.ptdevices.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_ptdevices_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ptdevices.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_ptdevices_level() -> PTDevicesResponse:
    """Mock a PTLevel device."""
    data = load_json_object_fixture("ptdevices_level.json", DOMAIN)
    return PTDevicesResponse(
        code=200,
        body=cast(PTDevicesResponseData, data),
    )


@pytest.fixture
def mock_ptdevices_interface(
    mock_ptdevices_level: PTDevicesResponse,
) -> Generator[AsyncMock]:
    """Mock a PTDevices Interface."""
    with (
        patch(
            "homeassistant.components.ptdevices.Interface",
            autospec=True,
        ) as mock_interface,
        patch(
            "homeassistant.components.ptdevices.config_flow.Interface",
            new=mock_interface,
        ),
    ):
        interface = mock_interface.return_value
        interface.get_data.return_value = mock_ptdevices_level

        yield interface


@pytest.fixture
def mock_ptdevices_config_entry() -> MockConfigEntry:
    """Return a mocked ptdevice configuration entry."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="User Name",
        data={
            CONF_API_TOKEN: "test-api-token",
        },
        unique_id="1234",
    )
