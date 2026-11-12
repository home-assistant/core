"""Fixtures for the London Air tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from pylondonair import Authority, LondonAirData, Pollutant, Site
import pytest

UPDATED = datetime(2017, 8, 3, 3, 0, 0, tzinfo=ZoneInfo("Europe/London"))


@pytest.fixture
def london_air_data() -> LondonAirData:
    """Return London air data matching the historical API fixture."""
    merton = Authority(
        name="Merton",
        code="24",
        centre_latitude="51.415672",
        centre_longitude="-0.191814",
        sites=(
            Site(
                site_code="ME2",
                site_name="Merton Road",
                site_type="Roadside",
                latitude="51.4161384794862",
                longitude="-0.192230805042824",
                updated=UPDATED,
                pollutants=(
                    Pollutant(
                        code="PM10",
                        description="PM10 Particulate",
                        quality="Low",
                        index="2",
                        summary="PM10 is Low",
                        index_source="Trigger",
                    ),
                ),
                status="Low",
                number_of_pollutants=1,
                latitude_wgs84="6695236.54926",
                longitude_wgs84="-21399.0353321",
            ),
            Site(
                site_code="ME9",
                site_name="Morden Civic Centre 2",
                site_type="Roadside",
                latitude="51.40162",
                longitude="-0.19589212",
                updated=UPDATED,
                pollutants=(
                    Pollutant(
                        code="NO2",
                        description="Nitrogen Dioxide",
                        quality="Low",
                        index="1",
                        summary="NO2 is Low",
                        index_source="Measurement",
                    ),
                ),
                status="Low",
                number_of_pollutants=1,
                latitude_wgs84="6692543.79001",
                longitude_wgs84="-21810.7165116",
            ),
        ),
        status="Low",
        centre_latitude_wgs84="6695153.285882",
        centre_longitude_wgs84="-21352.636807",
    )
    city_of_london = Authority(
        name="City of London",
        code="7",
        centre_latitude="51.51333",
        centre_longitude="-0.088947",
        sites=(),
        status=None,
        centre_latitude_wgs84="6712603.132989",
        centre_longitude_wgs84="-9901.534748",
    )
    barnet = Authority(
        name="Barnet",
        code="3",
        centre_latitude="51.60904",
        centre_longitude="-0.20629",
        sites=(
            Site(
                site_code="BA1",
                site_name="Barnet Test Site",
                site_type="Background",
                latitude="51.61000",
                longitude="-0.20500",
                updated=UPDATED,
                pollutants=(),
                status="no_species_data",
                number_of_pollutants=0,
            ),
        ),
        status="Low",
    )
    return LondonAirData(
        group_name="London",
        time_to_live=38,
        authorities={
            "Barnet": barnet,
            "City of London": city_of_london,
            "Merton": merton,
        },
    )


@pytest.fixture
def mock_london_air_client() -> Generator[AsyncMock]:
    """Mock the London Air client."""
    with patch(
        "homeassistant.components.london_air.sensor.LondonAirClient"
    ) as mock_client_cls:
        mock_client_cls.return_value.async_update = AsyncMock()
        yield mock_client_cls.return_value
