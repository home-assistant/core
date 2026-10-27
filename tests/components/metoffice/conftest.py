"""Fixtures for Met Office weather integration tests."""

from unittest.mock import patch

from datapoint.exceptions import APIException
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.metoffice.const import DOMAIN

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
