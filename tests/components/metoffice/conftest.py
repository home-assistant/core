"""Fixtures for Met Office weather integration tests."""
from unittest.mock import patch

from datapoint.exceptions import APIException
import pytest

from tests.common import mock_coro


@pytest.fixture()
def mock_simple_manager_fail():
    """Mock datapoint Manager with default values for testing in config_flow."""
    with patch("datapoint.Manager") as mock_manager:
        instance = mock_manager.return_value
        instance.get_nearest_forecast_site.return_value = mock_coro(
            exception=APIException
        )
        instance.get_forecast_for_site.return_value = mock_coro(exception=APIException)
        instance.latitude = None
        instance.longitude = None
        instance.site = None
        instance.site_id = None
        instance.site_name = None
        instance.now = None

        yield mock_manager
