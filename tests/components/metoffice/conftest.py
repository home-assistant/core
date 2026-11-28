"""Fixtures for Met Office weather integration tests."""

import json
from unittest.mock import patch

from datapoint.exceptions import APIException
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_json_object_fixture
import requests_mock
from requests_mock.adapter import _Matcher

from homeassistant.components.metoffice.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import (
    METOFFICE_CONFIG_KINGSLYNN,
    METOFFICE_CONFIG_WAVERTREE,
    TEST_LATITUDE_KINGSLYNN,
    TEST_LATITUDE_WAVERTREE,
    TEST_LONGITUDE_KINGSLYNN,
    TEST_LONGITUDE_WAVERTREE,
)


@pytest.fixture
def mock_simple_manager_fail():
    """Mock datapoint Manager with default values for testing in config_flow."""
    with patch(
        "homeassistant.components.metoffice.config_flow.Manager"
    ) as mock_manager:
        instance = mock_manager.return_value
        instance.get_forecast = APIException()
        instance.latitude = None
        instance.longitude = None
        instance.site = None
        instance.site_id = None
        instance.site_name = None
        instance.now = None

        yield mock_manager


@pytest.fixture(name="entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock configuration entry."""
    return MockConfigEntry(
        title="Wavertree",
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
        version=2,
        unique_id=f"{TEST_LATITUDE_WAVERTREE}_{TEST_LONGITUDE_WAVERTREE}",
    )


@pytest.fixture(name="entry2")
def mock_config_entry2() -> MockConfigEntry:
    """Mock configuration entry."""
    return MockConfigEntry(
        title="Wavertree",
        domain=DOMAIN,
        data=METOFFICE_CONFIG_KINGSLYNN,
        version=2,
        unique_id=f"{TEST_LATITUDE_KINGSLYNN}_{TEST_LONGITUDE_KINGSLYNN}",
    )


@pytest.fixture
async def wavertree_data(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> dict[str, _Matcher]:
    """Mock data for the Wavertree location."""
    # all metoffice test data encapsulated in here
    mock_json = await async_load_json_object_fixture(hass, "metoffice.json", DOMAIN)
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])

    wavertree_hourly_mock = requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        text=wavertree_hourly,
    )
    wavertree_daily_mock = requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text=wavertree_daily,
    )
    return {
        "wavertree_hourly_mock": wavertree_hourly_mock,
        "wavertree_daily_mock": wavertree_daily_mock,
    }
