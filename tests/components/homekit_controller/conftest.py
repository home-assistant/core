"""HomeKit controller session fixtures."""
import datetime
from unittest import mock

from aiohomekit.testing import FakeController
import asynctest
import pytest


@pytest.fixture
def utcnow(request):
    """Freeze time at a known point."""
    start_dt = datetime.datetime(2019, 1, 1, 0, 0, 0)
    with mock.patch("homeassistant.util.dt.utcnow") as dt_utcnow:
        dt_utcnow.return_value = start_dt
        yield dt_utcnow


@pytest.fixture
def controller(hass):
    """Replace aiohomekit.Controller with an instance of aiohomekit.testing.FakeController."""
    instance = FakeController()
    with asynctest.patch("aiohomekit.Controller", return_value=instance):
        yield instance
