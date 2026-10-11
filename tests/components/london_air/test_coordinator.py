"""Tests for the London Air coordinator parsing."""

from typing import Any

from homeassistant.components.london_air.coordinator import (
    NO_SPECIES_DATA,
    parse_api_response,
)


def _site(species: list[dict[str, str]]) -> dict[str, Any]:
    """Build a monitoring site payload."""
    return {
        "@BulletinDate": "2024-01-01",
        "@Latitude": "51.4",
        "@Longitude": "-0.1",
        "@SiteCode": "SITE1",
        "@SiteName": "London-Merton Test Site",
        "@SiteType": "Urban",
        "Species": species,
    }


def _payload(authority: str, site: dict[str, Any]) -> dict[str, Any]:
    """Build an API payload with a single authority and site."""
    return {
        "HourlyAirQualityIndex": {
            "LocalAuthority": [
                {
                    "@LocalAuthorityName": authority,
                    "Site": site,
                }
            ]
        }
    }


def test_parse_api_response_unknown_authority() -> None:
    """Test that an unknown authority is skipped."""
    result = parse_api_response(_payload("NotARealAuthority", _site([])))
    assert "NotARealAuthority" not in result
    assert all(sites == [] for sites in result.values())


def test_parse_api_response_site_as_dict() -> None:
    """Test that a single Site dict is wrapped in a list."""
    result = parse_api_response(_payload("Merton", _site([])))
    assert len(result["Merton"]) == 1
    assert result["Merton"][0]["site_code"] == "SITE1"
    assert result["Merton"][0]["site_name"] == "Merton Test Site"


def test_parse_api_response_no_data_species() -> None:
    """Test that species with no data are skipped."""
    species = [
        {
            "@AirQualityBand": "No data",
            "@SpeciesCode": "NO2",
            "@SpeciesDescription": "Nitrogen Dioxide",
            "@AirQualityIndex": "0",
        }
    ]
    result = parse_api_response(_payload("Merton", _site(species)))
    parsed_site = result["Merton"][0]
    assert parsed_site["pollutants"] == [NO_SPECIES_DATA]
    assert parsed_site["pollutants_status"] == NO_SPECIES_DATA
    assert parsed_site["number_of_pollutants"] == 0
