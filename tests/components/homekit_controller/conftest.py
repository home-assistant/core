"""HomeKit controller session fixtures."""

import datetime
import unittest.mock

from aiohomekit.testing import FakeController
from freezegun import freeze_time
import pytest

import homeassistant.util.dt as dt_util

from tests.components.light.conftest import mock_light_profiles  # noqa: F401

pytest.register_assert_rewrite("tests.components.homekit_controller.common")


@pytest.fixture(autouse=True)
def freeze_time_in_future(request):
    """Freeze time at a known point."""
    now = dt_util.utcnow()
    start_dt = datetime.datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=now.tzinfo)
    with freeze_time(start_dt) as frozen_time:
        yield frozen_time


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
