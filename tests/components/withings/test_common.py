"""Tests for the Withings component."""
import datetime
import nokia
import callee
from asynctest import patch, MagicMock
from homeassistant.components.withings import (
    WithingsDataManager
)
from tests.common import get_test_home_assistant


class TestWithingsDataManager:
    """Tests the data manager class."""

    def setup_method(self):
        """Set up the test."""
        self.hass = get_test_home_assistant()
        self.api = nokia.NokiaApi.__new__(nokia.NokiaApi)
        self.api.get_measures = MagicMock()
        self.api.get_sleep = MagicMock()

    def teardown_method(self):
        """Tear down the test."""
        self.hass.stop()

    async def test_async_update_measures(self):
        """Test method."""
        data_manager = WithingsDataManager(
            'person_1',
            self.api
        )

        self.api.get_measures = MagicMock(return_value='DATA')
        results1 = await data_manager.async_update_measures()
        self.api.get_measures.assert_called()
        assert results1 == 'DATA'

        self.api.get_measures.reset_mock()

        self.api.get_measures = MagicMock(return_value='DATA_NEW')
        await data_manager.async_update_measures()
        self.api.get_measures.assert_not_called()

    async def test_async_update_sleep(self):
        """Test method."""
        data_manager = WithingsDataManager(
            'person_1',
            self.api
        )

        with patch('time.time', return_value=100000.101):
            self.api.get_sleep = MagicMock(return_value='DATA')
            results1 = await data_manager.async_update_sleep()
            self.api.get_sleep.assert_called_with(
                startdate=78400,
                enddate=100000
            )
            assert results1 == 'DATA'

            self.api.get_sleep.reset_mock()

            self.api.get_sleep = MagicMock(return_value='DATA_NEW')
            await data_manager.async_update_sleep()
            self.api.get_sleep.assert_not_called()

    async def test_async_update_sleep_summary(self):
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
            self.api
        )

        self.api.get_sleep_summary = MagicMock(return_value='DATA')
        results1 = await data_manager.async_update_sleep_summary()
        self.api.get_sleep_summary.assert_called_with(
            lastupdate=callee.And(
                callee.GreaterOrEqualTo(yesterday_noon_timestamp),
                callee.LessThan(yesterday_noon_timestamp + 10)
            )
        )
        assert results1 == 'DATA'

        self.api.get_sleep_summary.reset_mock()

        self.api.get_sleep_summary = MagicMock(return_value='DATA_NEW')
        await data_manager.async_update_sleep_summary()
        self.api.get_sleep_summary.assert_not_called()
