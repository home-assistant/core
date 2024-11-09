"""Common fixtures for the Ambient Weather Network integration tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aioambient import OpenAPI
import pytest

from homeassistant.components.ambient_network.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ambient_network.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="devices_by_location", scope="package")
def devices_by_location_fixture() -> list[dict[str, Any]]:
    """Return result of OpenAPI get_devices_by_location() call."""
    return load_json_array_fixture(
        "devices_by_location_response.json", "ambient_network"
    )


def mock_device_details_callable(mac_address: str) -> dict[str, Any]:
    """Return result of OpenAPI get_device_details() call."""
    return load_json_object_fixture(
        f"device_details_response_{mac_address[0].lower()}.json", "ambient_network"
    )


@pytest.fixture(name="open_api")
def mock_open_api() -> OpenAPI:
    """Mock OpenAPI object."""
    return Mock(
        get_device_details=AsyncMock(side_effect=mock_device_details_callable),
    )


@pytest.fixture(name="aioambient")
async def mock_aioambient(open_api: OpenAPI):
    """Mock aioambient library."""
    with (
        patch(
            "homeassistant.components.ambient_network.config_flow.OpenAPI",
            return_value=open_api,
        ),
        patch(
            "homeassistant.components.ambient_network.OpenAPI",
            return_value=open_api,
        ),
    ):
        yield


@pytest.fixture(name="config_entry")
def config_entry_fixture(request: pytest.FixtureRequest) -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Station {request.param[0]}",
        data={"mac": request.param},
    )


async def setup_platform(
    expected_outcome: bool,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Load the Ambient Network integration with the provided OpenAPI and config entry."""

    config_entry.add_to_hass(hass)
    assert (
        await hass.config_entries.async_setup(config_entry.entry_id) == expected_outcome
    )
    await hass.async_block_till_done()
