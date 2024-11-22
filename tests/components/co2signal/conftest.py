"""Fixtures for Electricity maps integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.co2signal.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import VALID_RESPONSE

from tests.common import MockConfigEntry


@pytest.fixture(name="electricity_maps")
def mock_electricity_maps() -> Generator[MagicMock]:
    """Mock the ElectricityMaps client."""

    with (
        patch(
            "homeassistant.components.co2signal.ElectricityMaps",
            autospec=True,
        ) as electricity_maps,
        patch(
            "homeassistant.components.co2signal.config_flow.ElectricityMaps",
            new=electricity_maps,
        ),
    ):
        client = electricity_maps.return_value
        client.latest_carbon_intensity_by_coordinates.return_value = VALID_RESPONSE
        client.latest_carbon_intensity_by_country_code.return_value = VALID_RESPONSE

        yield client


@pytest.fixture(name="config_entry")
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a MockConfigEntry for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "api_key", "location": ""},
        entry_id="904a74160aa6f335526706bee85dfb83",
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, electricity_maps: AsyncMock
) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
