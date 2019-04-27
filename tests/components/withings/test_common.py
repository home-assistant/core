"""Tests for the Withings component."""
import datetime

from asynctest import patch, MagicMock
import callee
import nokia
import pytest

from homeassistant.components.withings.common import (
    WithingsDataManager,
)


@pytest.fixture(name='nokia_api')
def api_fixture():
    """Provide nokia api."""
    nokia_api = nokia.NokiaApi.__new__(nokia.NokiaApi)
    nokia_api.get_measures = MagicMock()
    nokia_api.get_sleep = MagicMock()
    return nokia_api


async def test_async_update_measures(nokia_api):
    """Test method."""
    data_manager = WithingsDataManager(
        'person_1',
        nokia_api
    )

    nokia_api.get_measures = MagicMock(return_value='DATA')
    results1 = await data_manager.async_update_measures()
    nokia_api.get_measures.assert_called_with()
    assert results1 == 'DATA'

    nokia_api.get_measures.reset_mock()

    nokia_api.get_measures = MagicMock(return_value='DATA_NEW')
    await data_manager.async_update_measures()
    nokia_api.get_measures.assert_not_called()


async def test_async_update_sleep(nokia_api):
    """Test method."""
    data_manager = WithingsDataManager(
        'person_1',
        nokia_api
    )

    with patch('time.time', return_value=100000.101):
        nokia_api.get_sleep = MagicMock(return_value='DATA')
        results1 = await data_manager.async_update_sleep()
        nokia_api.get_sleep.assert_called_with(
            startdate=78400,
            enddate=100000
        )
        assert results1 == 'DATA'

        nokia_api.get_sleep.reset_mock()

        nokia_api.get_sleep = MagicMock(return_value='DATA_NEW')
        await data_manager.async_update_sleep()
        nokia_api.get_sleep.assert_not_called()


async def test_async_update_sleep_summary(nokia_api):
    """Test method."""
    now = datetime.datetime.utcnow()
    noon = datetime.datetime(
        now.year, now.month, now.day,
        12, 0, 0, 0,
        datetime.timezone.utc
    )
    yesterday_noon_timestamp = noon.timestamp() - 86400

    data_manager = WithingsDataManager(
        'person_1',
        nokia_api
    )

    nokia_api.get_sleep_summary = MagicMock(return_value='DATA')
    results1 = await data_manager.async_update_sleep_summary()
    nokia_api.get_sleep_summary.assert_called_with(
        lastupdate=callee.And(
            callee.GreaterOrEqualTo(yesterday_noon_timestamp),
            callee.LessThan(yesterday_noon_timestamp + 10)
        )
    )
    assert results1 == 'DATA'

    nokia_api.get_sleep_summary.reset_mock()

    nokia_api.get_sleep_summary = MagicMock(return_value='DATA_NEW')
    await data_manager.async_update_sleep_summary()
    nokia_api.get_sleep_summary.assert_not_called()
