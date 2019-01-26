"""HomeKit controller session fixtures."""
import datetime
from unittest import mock

import pytest


@pytest.fixture
def utcnow(request):
    """Freeze time at a known point."""
    start_dt = datetime.datetime(2019, 1, 1, 0, 0, 0)
    patcher = mock.patch('homeassistant.util.dt.utcnow', return_value=start_dt)
    patcher.start()
    request.addfinalizer(patcher.stop)
    return start_dt
