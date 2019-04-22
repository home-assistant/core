"""Common code for Withings."""
import time
import datetime
import logging
from homeassistant.util import Throttle
from homeassistant.components.withings import (
    const
)

_LOGGER = logging.getLogger(const.LOG_NAMESPACE)


class WithingsDataManager:
    """A class representing an Withings cloud service connection."""

    def __init__(self, slug: str, api):
        """Constructor."""
        self._api = api
        self._slug = slug

        self._measures = None
        self._sleep = None
        self._sleep_summary = None

        self.sleep_summary_last_update_parameter = None

    def get_slug(self) -> str:
        """Get the slugified profile the data is for."""
        return self._slug

    def get_api(self):
        """Get the api object."""
        return self._api

    def get_measures(self):
        """Get the current measures data."""
        return self._measures

    def get_sleep(self):
        """Get the current sleep data."""
        return self._sleep

    def get_sleep_summary(self):
        """Get the current sleep summary data."""
        return self._sleep_summary

    @Throttle(const.SCAN_INTERVAL)
    async def async_refresh_token(self):
        """Refresh the api token."""
        current_time = int(time.time())
        expiration_time = int(self._api.credentials.token_expiry)

        if expiration_time - 1200 > current_time:
            _LOGGER.debug('No need to refresh access token.')
            return

        _LOGGER.debug('Refreshing access token.')
        api_client = self._api.client
        api_client.refresh_token(
            api_client.auto_refresh_url
        )

    @Throttle(const.SCAN_INTERVAL)
    async def async_update_measures(self):
        """Update the measures data."""
        _LOGGER.debug('async_update_measures')

        self._measures = self._api.get_measures()

        return self._measures

    @Throttle(const.SCAN_INTERVAL)
    async def async_update_sleep(self):
        """Update the sleep data."""
        _LOGGER.debug('async_update_sleep')

        end_date = int(time.time())
        start_date = end_date - (6 * 60 * 60)

        self._sleep = self._api.get_sleep(
            startdate=start_date,
            enddate=end_date
        )

        return self._sleep

    @Throttle(const.SCAN_INTERVAL)
    async def async_update_sleep_summary(self):
        """Update the sleep summary data."""
        _LOGGER.debug('async_update_sleep_summary')

        now = datetime.datetime.utcnow()
        yesterday = now - datetime.timedelta(days=1)
        yesterday_noon = datetime.datetime(
            yesterday.year, yesterday.month, yesterday.day,
            12, 0, 0, 0,
            datetime.timezone.utc
        )

        _LOGGER.debug(
            'Getting sleep summary data since: %s.',
            yesterday.strftime('%Y-%m-%d %H:%M:%S UTC')
        )

        self._sleep_summary = self._api.get_sleep_summary(
            lastupdate=yesterday_noon.timestamp()
        )

        return self._sleep_summary
