"""Common code for Withings."""
import time
import datetime
import logging
import re

import nokia
from requests_oauthlib import TokenUpdated

from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import slugify, Throttle
from . import const

_LOGGER = logging.getLogger(const.LOG_NAMESPACE)
NOT_AUTHENTICATED_ERROR = re.compile("^Error Code (100|101|102|200|401)$", re.IGNORECASE)  # pylint: disable=line-too-long  # noqa: E501


class NotAuthenticatedError(Exception):
    """Raise when not authenticated with the service."""

    pass


class ServiceError(Exception):
    """Raise when the service has an error."""

    pass


class WithingsDataManager:
    """A class representing an Withings cloud service connection."""

    service_available = None

    def __init__(self, profile: str, api: nokia.NokiaApi):
        """Constructor."""
        self._api = api
        self._profile = profile
        self._slug = slugify(profile)

        self._measures = None
        self._sleep = None
        self._sleep_summary = None

        self.sleep_summary_last_update_parameter = None

    @property
    def profile(self) -> str:
        """Get the profile."""
        return self._profile

    @property
    def slug(self) -> str:
        """Get the slugified profile the data is for."""
        return self._slug

    @property
    def api(self):
        """Get the api object."""
        return self._api

    @property
    def measures(self):
        """Get the current measures data."""
        return self._measures

    @property
    def sleep(self):
        """Get the current sleep data."""
        return self._sleep

    @property
    def sleep_summary(self):
        """Get the current sleep summary data."""
        return self._sleep_summary

    @staticmethod
    def print_service_unavailable():
        """Print the service is unavailable (once) to the log."""
        if WithingsDataManager.service_available is not False:
            _LOGGER.error(
                "Looks like the service is not available at the moment"
            )
            WithingsDataManager.service_available = False
            return True

    @staticmethod
    def print_service_available():
        """Print the service is available (once) to to the log."""
        if WithingsDataManager.service_available is not True:
            _LOGGER.info("Looks like the service is available again")
            WithingsDataManager.service_available = True
            return True

    @staticmethod
    async def async_call(function, is_first_call=True):
        """Call an api method and handle the result."""
        try:
            _LOGGER.debug("Running call.")
            result = await function()
            WithingsDataManager.print_service_available()
            return result

        except TokenUpdated:
            WithingsDataManager.print_service_available()
            if not is_first_call:
                raise ServiceError(
                    "Stuck in a token update loop. This should never happen"
                )

            _LOGGER.info("Token updated, re-running call.")
            return await WithingsDataManager.async_call(function, False)

        except Exception as ex:  # pylint: disable=broad-except
            # Service error, probably not authenticated.
            if NOT_AUTHENTICATED_ERROR.match(str(ex)):
                raise NotAuthenticatedError()

            # Probably a network error.
            WithingsDataManager.print_service_unavailable()
            raise PlatformNotReady(ex)

    @Throttle(const.SCAN_INTERVAL)
    async def async_check_authenticated(self):
        """Check if the user is authenticated."""
        async def function():
            return self._api.request('user', 'getdevice', version='v2')

        return await WithingsDataManager.async_call(function)

    @Throttle(const.SCAN_INTERVAL)
    async def async_update_measures(self):
        """Update the measures data."""
        async def function():
            return self._api.get_measures()

        self._measures = await WithingsDataManager.async_call(function)

        return self._measures

    @Throttle(const.SCAN_INTERVAL)
    async def async_update_sleep(self):
        """Update the sleep data."""
        end_date = int(time.time())
        start_date = end_date - (6 * 60 * 60)

        async def function():
            return self._api.get_sleep(
                startdate=start_date,
                enddate=end_date
            )

        self._sleep = await WithingsDataManager.async_call(function)

        return self._sleep

    @Throttle(const.SCAN_INTERVAL)
    async def async_update_sleep_summary(self):
        """Update the sleep summary data."""
        now = datetime.datetime.utcnow()
        yesterday = now - datetime.timedelta(days=1)
        yesterday_noon = datetime.datetime(
            yesterday.year, yesterday.month, yesterday.day,
            12, 0, 0, 0,
            datetime.timezone.utc
        )

        _LOGGER.debug(
            'Getting sleep summary data since: %s',
            yesterday.strftime('%Y-%m-%d %H:%M:%S UTC')
        )

        async def function():
            return self._api.get_sleep_summary(
                lastupdate=yesterday_noon.timestamp()
            )

        self._sleep_summary = await WithingsDataManager.async_call(function)

        return self._sleep_summary
