"""Tests for the station names of Spain fuel prices (Geoportal Gasolineras)."""

from aioprecioscarburantes import SaleType, Station
import pytest

from homeassistant.components.geoportal_gasolineras.names import (
    brand_name,
    municipality_name,
    station_name,
)


@pytest.mark.parametrize(
    ("municipality", "expected"),
    [
        ("Roda de Andalucía (La)", "La Roda de Andalucía"),
        ("Rinconada (La)", "La Rinconada"),
        ("Palmas de Gran Canaria (Las)", "Las Palmas de Gran Canaria"),
        ("Hospitalet de Llobregat (L')", "L'Hospitalet de Llobregat"),
        ("Sevilla", "Sevilla"),
    ],
)
def test_municipality_name(municipality: str, expected: str) -> None:
    """Test the article in brackets moves to the front."""
    assert municipality_name(municipality) == expected


@pytest.mark.parametrize(
    ("brand", "expected"), [("REPSOL", "Repsol"), ("BP", "BP"), ("CEPSA", "Cepsa")]
)
def test_brand_name(brand: str, expected: str) -> None:
    """Test brands are title case except short acronyms."""
    assert brand_name(brand) == expected


def _station(brand: str, municipality: str) -> Station:
    return Station(
        id="1",
        brand=brand,
        address="CALLE MAYOR, 1",
        locality="",
        municipality=municipality,
        municipality_id="1",
        province="",
        province_id="1",
        postal_code="",
        schedule="",
        latitude=None,
        longitude=None,
        sale_type=SaleType.PUBLIC,
    )


def test_brand_with_town() -> None:
    """Test the town is not repeated when the brand includes it."""
    assert station_name(_station("GAFISUR ANTEQUERA", "Antequera"), set()) == (
        "Gafisur Antequera"
    )
    assert station_name(_station("REPSOL", "Antequera"), set()) == "Repsol Antequera"
