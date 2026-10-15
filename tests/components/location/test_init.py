"""Tests for location based integration matching."""

from collections.abc import Generator
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.location.const import DOMAIN
from homeassistant.components.location.region import available_regions, match_regions
from homeassistant.core import HomeAssistant
from homeassistant.generated import locations as generated_locations
from homeassistant.setup import async_setup_component

from tests.typing import MockHAClientWebSocket, WebSocketGenerator

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


async def _get_integrations(client: MockHAClientWebSocket) -> dict[str, Any]:
    """Return the integrations serving the home location."""
    await client.send_json_auto_id({"type": "location/integrations"})
    response = await client.receive_json()
    assert response["success"]
    return response["result"]


@pytest.mark.parametrize(
    ("latitude", "longitude", "integrations"),
    [
        pytest.param(*AMSTERDAM, {"test": ["NL"]}, id="inside_region"),
        pytest.param(*ANTWERP, {}, id="outside_region"),
        pytest.param(0, 0, {}, id="core_config_default_location"),
        pytest.param(52.3731339, 4.8903147, {}, id="onboarding_default_location"),
    ],
)
async def test_integrations(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    latitude: float,
    longitude: float,
    integrations: dict[str, list[str]],
) -> None:
    """Test getting the integrations serving the home location."""
    hass.config.latitude = latitude
    hass.config.longitude = longitude
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)

    assert await _get_integrations(client) == integrations


@pytest.mark.parametrize("locations", [{"NL": ["test"], "RANDSTAD": ["other", "test"]}])
async def test_overlapping_regions(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, tmp_path: Path
) -> None:
    """Test integrations list every region containing the home location."""
    randstad = tmp_path / "RANDSTAD.geojson"
    randstad.write_text(
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [[4, 51.8], [5.2, 51.8], [5.2, 52.5], [4, 52.5], [4, 51.8]]
                ],
            }
        )
    )
    hass.config.latitude, hass.config.longitude = AMSTERDAM
    with patch(
        "homeassistant.components.location.available_regions",
        return_value={**available_regions(), "RANDSTAD": randstad},
    ):
        assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)

    assert await _get_integrations(client) == {
        "other": ["RANDSTAD"],
        "test": ["NL", "RANDSTAD"],
    }


@pytest.mark.parametrize("locations", [{"NL": ["test"], "XX": ["test", "other"]}])
async def test_unknown_region(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test regions without a region file are ignored."""
    hass.config.latitude, hass.config.longitude = AMSTERDAM
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)

    assert "Integrations test, other use unknown region XX" in caplog.text
    assert await _get_integrations(client) == {"test": ["NL"]}


async def test_home_location_updated(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the integrations follow the home location."""
    hass.config.latitude, hass.config.longitude = AMSTERDAM
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.location.match_regions", wraps=match_regions
    ) as mock_match_regions:
        assert await _get_integrations(client) == {"test": ["NL"]}
        assert await _get_integrations(client) == {"test": ["NL"]}
        # The regions are only matched again when the home location changes
        assert mock_match_regions.call_count == 1

        await hass.config.async_update(latitude=ANTWERP[0], longitude=ANTWERP[1])
        assert await _get_integrations(client) == {}

        await hass.config.async_update(latitude=ENSCHEDE[0], longitude=ENSCHEDE[1])
        assert await _get_integrations(client) == {"test": ["NL"]}
        assert mock_match_regions.call_count == 3


async def test_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test only admins can get the integrations."""
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json_auto_id({"type": "location/integrations"})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
