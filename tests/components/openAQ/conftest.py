"""Provide common openAQ fixtures."""
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, Mock, patch

from openaq._sync.models.locations import LocationsResponse
from openaq.shared.responses import (
    Coordinates,
    CountryBase,
    Datetime,
    InstrumentBase,
    Location,
    Meta,
    OwnerBase,
    ParameterBase,
    ProviderBase,
    SensorBase,
)
import pytest

from homeassistant.components.openAQ.const import API_KEY_ID, DOMAIN, LOCATION_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

ComponentSetup = Callable[[MockConfigEntry], Awaitable[None]]


class TestingOpenAQ:
    def __init__(self, api_key):
        self.api_key = api_key
        self.locations = {
            10496: LocationsResponse(
                meta=Meta(name="openaq-api", website="/", page=1, limit=100, found=1),
                results=[
                    Location(
                        id=10496,
                        name="SE0004A",
                        locality="Västra Götaland",
                        timezone="Europe/Stockholm",
                        country=CountryBase(id=116, code="SE", name="Sweden"),
                        owner=OwnerBase(id=4, name="Unknown Governmental Organization"),
                        provider=ProviderBase(id=197, name="EEA Sweden"),
                        is_mobile=False,
                        is_monitor=True,
                        instruments=[InstrumentBase(id=2, name="Government Monitor")],
                        sensors=[
                            SensorBase(
                                id=34818,
                                name="o3 µg/m³",
                                parameter=ParameterBase(
                                    id=3,
                                    name="o3",
                                    units="µg/m³",
                                    display_name="O₃ mass",
                                ),
                            ),
                            SensorBase(
                                id=34820,
                                name="pm25 µg/m³",
                                parameter=ParameterBase(
                                    id=2,
                                    name="pm25",
                                    units="µg/m³",
                                    display_name="PM2.5",
                                ),
                            ),
                            SensorBase(
                                id=34819,
                                name="pm10 µg/m³",
                                parameter=ParameterBase(
                                    id=1,
                                    name="pm10",
                                    units="µg/m³",
                                    display_name="PM10",
                                ),
                            ),
                            SensorBase(
                                id=34817,
                                name="no2 µg/m³",
                                parameter=ParameterBase(
                                    id=5,
                                    name="no2",
                                    units="µg/m³",
                                    display_name="NO₂ mass",
                                ),
                            ),
                        ],
                        coordinates=Coordinates(
                            latitude=57.70860999951551, longitude=11.97
                        ),
                        bounds=[11.97, 57.70860999951551, 11.97, 57.70860999951551],
                        distance=None,
                        datetime_first=Datetime(
                            utc="2020-05-06T22:00:00+00:00",
                            local="2020-05-07T00:00:00+02:00",
                        ),
                        datetime_last=Datetime(
                            utc="2023-12-08T07:00:00+00:00",
                            local="2023-12-08T08:00:00+01:00",
                        ),
                    )
                ],
            )
        }


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Create OpenSky entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="openAQ",
        data={
            API_KEY_ID: "n444fd45sb45uhdss545465ad",
            LOCATION_ID: 10496,
        },
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
) -> Callable[[MockConfigEntry], Awaitable[None]]:
    """Fixture for setting up the component."""

    async def func(mock_config_entry: MockConfigEntry) -> None:
        mock_config_entry.add_to_hass(hass)
        with patch("openaq.OpenAQ.__new__", return_value=TestingOpenAQ("10496")):
            assert await async_setup_component(hass, DOMAIN, {})
            await hass.async_block_till_done()

    return func


@pytest.fixture
def mock_aq_client():
    """Fixture to create a basic mock AQClient."""
    with patch("homeassistant.components.openAQ.aq_client.AQClient") as mock_client:
        yield mock_client.return_value


@pytest.fixture
def mock_aq_client_for_config_flow(mock_aq_client):
    """Fixture to provide mocked AQClient with predefined data for config flow tests."""
    # Define standard mocked responses
    mock_aq_client.get_device.side_effect = [
        # Successful data retrieval
        AsyncMock(
            return_value=Mock(
                sensors=[
                    {
                        "type": "pm25",
                        "value": 15,
                        "last_updated": "2023-11-30T12:00:00",
                    },
                    {
                        "type": "pm10",
                        "value": 20,
                        "last_updated": "2023-11-30T12:00:00",
                    },
                ],
                locality="Visby",
            )
        ),
        # Location not found (empty sensors list)
        AsyncMock(return_value=Mock(sensors=[], locality="")),
        # Response for invalid or empty API key: Simulate no sensor data and no locality info
        AsyncMock(return_value=Mock(sensors=[], locality="")),
    ]
    return mock_aq_client
