"""Tests for location based discovery."""

from collections.abc import Generator
from typing import Any
from unittest.mock import call, patch

import pytest

from homeassistant.components.location.const import DOMAIN
from homeassistant.config_entries import SOURCE_LOCATION, ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.generated import locations as generated_locations
from homeassistant.helpers.service_info.location import LocationServiceInfo
from homeassistant.setup import async_setup_component

from tests.common import MockModule, mock_config_flow, mock_integration, mock_platform

AMSTERDAM = (52.3731, 4.8922)
ENSCHEDE = (52.2215, 6.8937)
ANTWERP = (51.2194, 4.4025)


@pytest.fixture
def locations() -> dict[str, list[str]]:
    """Return the regions served by integrations."""
    return {"NL": ["test"]}


@pytest.fixture(autouse=True)
def mock_locations(locations: dict[str, list[str]]) -> Generator[None]:
    """Mock the generated locations."""
    with patch.dict(generated_locations.LOCATIONS, locations, clear=True):
        yield


class MockLocationFlow(ConfigFlow):
    """Config flow handling location discovery."""

    async def async_step_location(
        self, discovery_info: LocationServiceInfo
    ) -> ConfigFlowResult:
        """Handle location discovery."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovery."""
        return self.async_show_form(step_id="confirm")


@pytest.mark.parametrize(
    ("latitude", "longitude", "domains"),
    [
        pytest.param(*AMSTERDAM, ["test"], id="inside_region"),
        pytest.param(*ANTWERP, [], id="outside_region"),
        pytest.param(0, 0, [], id="default_location"),
    ],
)
async def test_discovery_at_start(
    hass: HomeAssistant, latitude: float, longitude: float, domains: list[str]
) -> None:
    """Test integrations serving the home location are discovered."""
    hass.config.latitude = latitude
    hass.config.longitude = longitude
    with patch(
        "homeassistant.components.location.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert mock_create_flow.mock_calls == [
        call(
            hass,
            domain,
            {"source": SOURCE_LOCATION},
            LocationServiceInfo(latitude=latitude, longitude=longitude, regions=["NL"]),
        )
        for domain in domains
    ]


@pytest.mark.parametrize("locations", [{"NL": ["test"], "XX": ["test", "other"]}])
async def test_unknown_region(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test regions without a region file are ignored."""
    hass.config.latitude, hass.config.longitude = AMSTERDAM
    with patch(
        "homeassistant.components.location.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert "Integrations test, other use unknown region XX" in caplog.text
    assert mock_create_flow.mock_calls == [
        call(
            hass,
            "test",
            {"source": SOURCE_LOCATION},
            LocationServiceInfo(
                latitude=AMSTERDAM[0], longitude=AMSTERDAM[1], regions=["NL"]
            ),
        )
    ]


async def test_home_location_updated(hass: HomeAssistant) -> None:
    """Test discovery follows the home location."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    hass.config.latitude, hass.config.longitude = AMSTERDAM

    with mock_config_flow("test", MockLocationFlow):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        [amsterdam_flow] = hass.config_entries.flow.async_progress_by_handler("test")

        # Unrelated updates and updates keeping the location are ignored
        await hass.config.async_update(location_name="Somewhere")
        await hass.config.async_update(latitude=AMSTERDAM[0])
        await hass.async_block_till_done()
        assert hass.config_entries.flow.async_progress_by_handler("test") == [
            amsterdam_flow
        ]

        await hass.config.async_update(latitude=ENSCHEDE[0], longitude=ENSCHEDE[1])
        await hass.async_block_till_done()
        [enschede_flow] = hass.config_entries.flow.async_progress_by_handler("test")
        assert enschede_flow["flow_id"] != amsterdam_flow["flow_id"]

        await hass.config.async_update(latitude=ANTWERP[0], longitude=ANTWERP[1])
        await hass.async_block_till_done()
        assert hass.config_entries.flow.async_progress_by_handler("test") == []
