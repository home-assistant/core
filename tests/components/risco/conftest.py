"""Fixtures for Risco tests."""
from unittest.mock import MagicMock, PropertyMock, patch

from pytest import fixture

from .util import zone_mock


@fixture
def two_zone_cloud():
    """Fixture to mock alarm with two zones."""
    zone_mocks = {0: zone_mock(), 1: zone_mock()}
    alarm_mock = MagicMock()
    with patch.object(
        zone_mocks[0], "id", new_callable=PropertyMock(return_value=0)
    ), patch.object(
        zone_mocks[0], "name", new_callable=PropertyMock(return_value="Zone 0")
    ), patch.object(
        zone_mocks[1], "id", new_callable=PropertyMock(return_value=1)
    ), patch.object(
        zone_mocks[1], "name", new_callable=PropertyMock(return_value="Zone 1")
    ), patch.object(
        alarm_mock,
        "zones",
        new_callable=PropertyMock(return_value=zone_mocks),
    ), patch(
        "homeassistant.components.risco.RiscoCloud.get_state",
        return_value=alarm_mock,
    ):
        yield zone_mocks
