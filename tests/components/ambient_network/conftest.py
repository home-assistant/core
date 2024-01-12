"""Common fixtures for the Ambient Weather Network integration tests."""

from collections.abc import Generator
import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aioambient import OpenAPI
import pytest

from homeassistant.components import ambient_network
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry(aioambient: AsyncMock) -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ambient_network.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="devices_by_location", scope="package")
def devices_by_location_fixture() -> list[dict[str, Any]]:
    """Define data returned by the OpenAPI get_devices_by_location() call."""
    return json.loads(
        load_fixture("devices_by_location_response.json", "ambient_network")
    )


@pytest.fixture(name="empty_devices_by_location", scope="package")
def devices_by_location_empty_fixture() -> list[dict[str, Any]]:
    """Define data returned by the OpenAPI get_devices_by_location() call if no stations are found."""
    return json.loads("[]")


def mock_device_details_callable(mac_address: str) -> dict[str, Any]:
    """Define data returned by the OpenAPI get_device_details() call."""
    if mac_address == "AA:AA:AA:AA:AA:AA:AA":
        return json.loads(
            load_fixture("device_details_response_a.json", "ambient_network")
        )
    return json.loads(load_fixture("device_details_response_b.json", "ambient_network"))


@pytest.fixture(name="open_api")
def mock_open_api(hass: HomeAssistant) -> OpenAPI:
    """Define a mock OpenAPI object."""
    return Mock(
        get_device_details=AsyncMock(side_effect=mock_device_details_callable),
    )


@pytest.fixture(name="aioambient")
async def mock_aioambient(open_api: OpenAPI):
    """Mock aioambient library."""
    with patch(
        "homeassistant.components.ambient_network.config_flow.OpenAPI",
        return_value=open_api,
    ), patch(
        "homeassistant.components.ambient_network.OpenAPI",
        return_value=open_api,
    ):
        yield


@pytest.fixture(name="config_entry")
def config_entry_fixture() -> MockConfigEntry:
    """Create a new config entry."""
    return MockConfigEntry(
        domain=ambient_network.DOMAIN,
        title="Station A1",
        data={"station_name": "Station A1", "mac_address": "AA:AA:AA:AA:AA:AA"},
    )


async def setup_platform(
    hass: HomeAssistant, open_api: OpenAPI, config_entry: MockConfigEntry
):
    """Load the Ambient Network integration with the provided OpenAPI."""

    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, ambient_network.DOMAIN, {})
    await hass.async_block_till_done()

    # Perform a coordinator refresh
    coordinator = hass.data[ambient_network.DOMAIN][config_entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    return
