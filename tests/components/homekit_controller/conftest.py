"""HomeKit controller session fixtures."""
import datetime
from unittest import mock
import unittest.mock

from aiohomekit.testing import FakeController
import pytest

import homeassistant.util.dt as dt_util

from tests.components.light.conftest import mock_light_profiles  # noqa: F401

pytest.register_assert_rewrite("tests.components.homekit_controller.common")


@pytest.fixture
def utcnow(request):
    """Freeze time at a known point."""
    now = dt_util.utcnow()
    start_dt = datetime.datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=now.tzinfo)
    with mock.patch("homeassistant.util.dt.utcnow") as dt_utcnow:
        dt_utcnow.return_value = start_dt
        yield dt_utcnow


@pytest.fixture
def controller(hass):
    """Replace aiohomekit.Controller with an instance of aiohomekit.testing.FakeController."""
    instance = FakeController()
    with unittest.mock.patch(
        "homeassistant.components.homekit_controller.utils.Controller",
        return_value=instance,
    ):
        yield instance


@pytest.fixture(autouse=True)
def hk_mock_async_zeroconf(mock_async_zeroconf):
    """Auto mock zeroconf."""


@pytest.fixture(autouse=True)
def auto_mock_bluetooth(mock_bluetooth):
    """Auto mock bluetooth."""
