"""Fixtures for Met Office weather integration tests."""
<<<<<<< HEAD
from datapoint.exceptions import APIException
import pytest

from tests.async_mock import patch
=======
from unittest.mock import patch

from datapoint.exceptions import APIException
import pytest

from tests.common import mock_coro
>>>>>>> Added further test cases to improve patch coverage. Now tests more negative cases, as well as the positive cases.


@pytest.fixture()
def mock_simple_manager_fail():
    """Mock datapoint Manager with default values for testing in config_flow."""
    with patch("datapoint.Manager") as mock_manager:
        instance = mock_manager.return_value
<<<<<<< HEAD
        instance.get_nearest_forecast_site.side_effect = APIException()
        instance.get_forecast_for_site.side_effect = APIException()
=======
        instance.get_nearest_forecast_site.return_value = mock_coro(
            exception=APIException
        )
        instance.get_forecast_for_site.return_value = mock_coro(exception=APIException)
>>>>>>> Added further test cases to improve patch coverage. Now tests more negative cases, as well as the positive cases.
        instance.latitude = None
        instance.longitude = None
        instance.site = None
        instance.site_id = None
        instance.site_name = None
        instance.now = None

        yield mock_manager
