"""Common code for Withings."""
import datetime
import logging
import re
import time

import nokia
from oauthlib.oauth2.rfc6749.errors import MissingTokenError
from requests_oauthlib import TokenUpdated

from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import slugify

from . import const

_LOGGER = logging.getLogger(const.LOG_NAMESPACE)
NOT_AUTHENTICATED_ERROR = re.compile(
    ".*(Error Code (100|101|102|200|401)|Missing access token parameter).*",
    re.IGNORECASE
)


class NotAuthenticatedError(Exception):
    """Raise when not authenticated with the service."""

    pass


class ServiceError(Exception):
    """Raise when the service has an error."""

    pass


class ThrottleData:
    """Throttle data."""

    def __init__(self, interval: int, data):
        """Constructor."""
        self._time = int(time.time())
        self._interval = interval
        self._data = data

    @property
    def time(self):
        """Get time created."""
        return self._time

    @property
    def interval(self):
        """Get interval."""
        return self._interval

    @property
    def data(self):
        """Get data."""
        return self._data

    def is_expired(self):
        """Is this data expired."""
        return int(time.time()) - self.time > self.interval


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
        self.throttle_data = {}

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
    def get_throttle_interval():
        """Get the throttle interval."""
        return const.THROTTLE_INTERVAL

    def get_throttle_data(self, domain: str) -> ThrottleData:
        """Get throttlel data."""
        return self.throttle_data.get(domain)

    def set_throttle_data(self, domain: str, throttle_data: ThrottleData):
        """Set throttle data."""
        self.throttle_data[domain] = throttle_data

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

    def call(self, function, is_first_call=True, throttle_domain=None):
        """Call an api method and handle the result."""
        throttle_data = self.get_throttle_data(throttle_domain)

        should_throttle = throttle_domain and \
            throttle_data and \
            not throttle_data.is_expired()

        try:
            if should_throttle:
                _LOGGER.debug(
                    "Throttling call for domain: %s",
                    throttle_domain
                )
                result = throttle_data.data
            else:
                _LOGGER.debug("Running call.")
                result = function()

                # Update throttle data.
                self.set_throttle_data(throttle_domain, ThrottleData(
                    self.get_throttle_interval(),
                    result
                ))

            WithingsDataManager.print_service_available()
            return result

        except TokenUpdated:
            WithingsDataManager.print_service_available()
            if not is_first_call:
                raise ServiceError(
                    "Stuck in a token update loop. This should never happen"
                )

            _LOGGER.info("Token updated, re-running call.")
            return self.call(function, False)

        except MissingTokenError as ex:
            raise NotAuthenticatedError(ex)

        except Exception as ex:  # pylint: disable=broad-except
            # Service error, probably not authenticated.
            if NOT_AUTHENTICATED_ERROR.match(str(ex)):
                raise NotAuthenticatedError(ex)

            # Probably a network error.
            WithingsDataManager.print_service_unavailable()
            raise PlatformNotReady(ex)

    def check_authenticated(self):
        """Check if the user is authenticated."""
        def function():
            return self._api.request('user', 'getdevice', version='v2')

        return self.call(function)

    def update_measures(self):
        """Update the measures data."""
        def function():
            return self._api.get_measures()

        self._measures = self.call(function, throttle_domain='update_measures')

        return self._measures

    def update_sleep(self):
        """Update the sleep data."""
        end_date = int(time.time())
        start_date = end_date - (6 * 60 * 60)

        def function():
            return self._api.get_sleep(
                startdate=start_date,
                enddate=end_date
            )

        self._sleep = self.call(function, throttle_domain='update_sleep')

        return self._sleep

    def update_sleep_summary(self):
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

        def function():
            return self._api.get_sleep_summary(
                lastupdate=yesterday_noon.timestamp()
            )

        self._sleep_summary = self.call(
            function,
            throttle_domain='update_sleep_summary'
        )

        return self._sleep_summary
