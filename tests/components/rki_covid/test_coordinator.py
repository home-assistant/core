"""Tests for the RKI Covid numbers Data Coordinator."""
from __future__ import annotations

from asyncio import TimeoutError
from datetime import timedelta
from unittest.mock import AsyncMock

from aiohttp import ClientError
import pytest
from rki_covid_parser.parser import RkiCovidParser

from homeassistant.components.rki_covid.coordinator import RkiCovidDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from tests.components.rki_covid import MOCK_COUNTRY, MOCK_DISTRICTS, MOCK_STATES


async def test_coordinator_update_interval(hass: HomeAssistant) -> None:
    """Test the update interval of the data update coordinator."""
    coordinator = RkiCovidDataUpdateCoordinator(hass)
    assert coordinator.update_interval == timedelta(hours=3)


async def test_fetch_districts(hass: HomeAssistant) -> None:
    """Test fetching districts from rki-covid-parser."""

    coordinator = RkiCovidDataUpdateCoordinator(hass)
    coordinator.parser = RkiCovidParser(async_get_clientsession(hass))
    coordinator.parser.load_data = AsyncMock(return_value=None)
    coordinator.parser.districts = MOCK_DISTRICTS
    coordinator.parser.states = MOCK_STATES
    coordinator.parser.country = MOCK_COUNTRY

    # update coordinator
    result = await coordinator._async_update_data()

    assert result is not None
    assert len(result) == 3

    # District
    assert result["SK Amberg"].state == "Bayern"
    assert result["SK Amberg"].population == 45678
    assert result["SK Amberg"].count == 12345
    assert result["SK Amberg"].deaths == 23456
    assert result["SK Amberg"].cases_per_week == 34567
    assert result["SK Amberg"].recovered == 0
    assert result["SK Amberg"].week_incidence == 75675.4
    assert result["SK Amberg"].cases_per100k == 27026.14
    assert result["SK Amberg"].new_cases == 0
    assert result["SK Amberg"].new_deaths == 0
    assert result["SK Amberg"].new_recovered == 0
    assert result["SK Amberg"].last_update == "01.01.2022, 00:00 Uhr"

    # State
    assert result["BL Bayern"].population == 99
    assert result["BL Bayern"].count == 88
    assert result["BL Bayern"].deaths == 77
    assert result["BL Bayern"].cases_per_week == 66
    assert result["BL Bayern"].recovered == 55
    assert result["BL Bayern"].week_incidence == 66666.7
    assert result["BL Bayern"].cases_per100k == 88888.89
    assert result["BL Bayern"].new_cases == 33
    assert result["BL Bayern"].new_deaths == 22
    assert result["BL Bayern"].new_recovered == 11
    assert result["BL Bayern"].last_update == "01.01.2022, 00:00 Uhr"

    # Country
    assert result["Deutschland"].population == 83129285
    assert result["Deutschland"].count == 7835451
    assert result["Deutschland"].deaths == 115337
    assert result["Deutschland"].cases_per_week == 94227
    assert result["Deutschland"].recovered == 6914679
    assert result["Deutschland"].week_incidence == 113.3
    assert result["Deutschland"].cases_per100k == 9425.62
    assert result["Deutschland"].new_cases == 192
    assert result["Deutschland"].new_deaths == 386
    assert result["Deutschland"].new_recovered == 182
    assert result["Deutschland"].last_update == "01.01.2022, 00:00 Uhr"


async def test_update_timeout(hass: HomeAssistant) -> None:
    """Test update timeout while fetching districts from rki-covid-parser."""

    coordinator = RkiCovidDataUpdateCoordinator(hass)
    coordinator.parser = RkiCovidParser(async_get_clientsession(hass))
    coordinator.parser.load_data = AsyncMock(side_effect=TimeoutError("mock timeout"))

    with pytest.raises(update_coordinator.UpdateFailed):
        await coordinator._async_update_data()


async def test_update_client_error(hass: HomeAssistant) -> None:
    """Test update client error while fetching districts from rki-covid-parser."""

    coordinator = RkiCovidDataUpdateCoordinator(hass)
    coordinator.parser = RkiCovidParser(async_get_clientsession(hass))
    coordinator.parser.load_data = AsyncMock(side_effect=ClientError("mock timeout"))

    with pytest.raises(update_coordinator.UpdateFailed):
        await coordinator._async_update_data()
