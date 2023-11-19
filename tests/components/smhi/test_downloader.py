"""Testing the functionality of the SmhiDownloader class."""

import aiohttp
from aioresponses import aioresponses
import pytest

from homeassistant.components.smhi import SmhiDownloader

# Mock data
mock_data = [
    {
        "id": 1,
        "normalProbability": "true",
        "event": {
            "sv": "Vind",
            "en": "Wind",
            "code": "WIND",
            "mhoClassification": {
                "sv": "Meteorologi",
                "en": "Meteorology",
                "code": "MET",
            },
        },
        "descriptions": [],
        "warningAreas": [
            {
                "id": 1,
                "approximateStart": "2021-09-16T08:00:00.000Z",
                "approximateEnd": "2021-09-20T08:00:00.000Z",
                "published": "2021-09-16T08:47:36.540Z",
                "normalProbability": "true",
                "areaName": {
                    "sv": "TEST Västra Götalands län",
                    "en": "TEST Västra Götaland County",
                },
                "warningLevel": {"sv": "Gul", "en": "Yellow", "code": "YELLOW"},
                "eventDescription": {"sv": "Vind", "en": "Wind", "code": "WIND"},
                "affectedAreas": [
                    {
                        "id": 14,
                        "sv": "Västra Götalands län",
                        "en": "Västra Götaland County",
                    }
                ],
                "descriptions": [
                    {
                        "title": {
                            "sv": "Händelsebeskrivning",
                            "en": "Description of incident",
                            "code": "INCIDENT",
                        },
                        "text": {
                            "sv": "TESTMEDDELANDE.",
                            "en": "TEST.",
                        },
                    },
                    {
                        "title": {
                            "sv": "Hur kan det påverka mig",
                            "en": "What to expect",
                            "code": "AFFECT",
                        },
                        "text": {
                            "sv": "TEST Begränsad framkomlighet på vägar på grund av nedfallna träd.\nRisk för förseningar inom buss-, tåg-, flyg- och färjetrafiken samt inställda avgångar.\nOmråden med luftburna elledningar kan påverkas och ge störningar i el- och teleförsörjningen.\nLösa föremål och tillfälliga konstruktioner riskerar att förflyttas eller skadas.\nVissa skador på skog (hyggeskanter och nygallrad skog). Enstaka träd eller grenar ramlar ner.",
                            "en": "TEST Risk for road blockages due to fallen trees.\nRisk of delays in bus-, train-, air- and ferry traffic as well as canceled departures.\nAreas with overground power lines can be affected and cause disturbances in the electricity- and telecommunications supply.\nLoose objects and temporary constructions are at risk of being moved or damaged.\nSome damage to forest (felling edges and newly thinned forest). Single trees or branches may fall down.",
                        },
                    },
                    {
                        "title": {"sv": "Var", "en": "Where", "code": "WHERE"},
                        "text": {
                            "sv": "TEST Hallands län, Skåne län, Kronobergs län, Blekinge län och Kalmar län, inklusive Öland.",
                            "en": "TEST Halland County, Skåne County, Kronoberg County, Blekinge County and Kalmar County, including Öland.",
                        },
                    },
                    {
                        "title": {
                            "sv": "Vad händer",
                            "en": "What happens",
                            "code": "HAPPENS",
                        },
                        "text": {
                            "sv": "TEST.",
                            "en": "TEST.",
                        },
                    },
                    {
                        "title": {
                            "sv": "Kommentar",
                            "en": "Comments",
                            "code": "COMMENTS",
                        },
                        "text": {
                            "sv": "TEST.",
                            "en": "TEST.",
                        },
                    },
                ],
                "area": {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [12.44751, 57.762799],
                                [13.161621, 57.809651],
                                [12.744141, 58.019737],
                                [12.44751, 57.762799],
                            ]
                        ],
                    },
                },
            }
        ],
    }
]


@pytest.mark.asyncio
async def test_successful_download():
    """Test if SmhiDownloader.fetch successfully downloads data for a valid URL."""
    downloader = SmhiDownloader()
    url = "http://example.com/weatherwarnings.json"

    with aioresponses() as m:
        m.get(url, status=200, payload=mock_data)
        async with aiohttp.ClientSession() as session:
            result = await downloader.fetch(session, url)
            assert result == mock_data


@pytest.mark.asyncio
async def test_non_200_response():
    """Test if SmhiDownloader.fetch correctly handles non-200 HTTP responses."""
    downloader = SmhiDownloader()
    url = "http://example.com/weatherwarnings.json"

    with aioresponses() as m:
        m.get(url, status=404)
        async with aiohttp.ClientSession() as session:
            result = await downloader.fetch(session, url)
            assert result is None


@pytest.mark.asyncio
async def test_download_json():
    """Test if SmhiDownloader.download_json correctly downloads and returns JSON data."""
    downloader = SmhiDownloader()
    url = "http://example.com/weatherwarnings.json"

    with aioresponses() as m:
        m.get(url, status=200, payload=mock_data)
        result = await downloader.download_json(url)
        assert result == mock_data
