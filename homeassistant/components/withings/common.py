"""Common code for Withings."""
import datetime
import logging
import re
import time
from typing import Any

from oauthlib.oauth2.rfc6749.errors import MissingTokenError
from withings_api import (
    WithingsApi,
    Credentials,
    SleepGetResponse,
    MeasureGetMeasResponse,
    SleepGetSummaryResponse,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt, slugify

from . import const

_LOGGER = logging.getLogger(const.LOG_NAMESPACE)
NOT_AUTHENTICATED_ERROR = re.compile(
    ".*(Error Code (100|101|102|200|401)|Missing access token parameter).*",
    re.IGNORECASE,
)


class NotAuthenticatedError(HomeAssistantError):
    """Raise when not authenticated with the service."""

    pass


class ServiceError(HomeAssistantError):
    """Raise when the service has an error."""

    pass


class ThrottleData:
    """Throttle data."""

    def __init__(self, interval: int, data: Any):
        """Constructor."""
        self._time = int(time.time())
        self._interval = interval
        self._data = data

    @property
    def time(self) -> int:
        """Get time created."""
        return self._time

    @property
    def interval(self) -> int:
        """Get interval."""
        return self._interval

    @property
    def data(self) -> Any:
        """Get data."""
        return self._data

    def is_expired(self) -> bool:
        """Is this data expired."""
        return int(time.time()) - self.time > self.interval


class WithingsDataManager:
    """A class representing an Withings cloud service connection."""

    service_available = None

    def __init__(self, hass: HomeAssistantType, profile: str, api: WithingsApi):
        """Constructor."""
        self._hass = hass
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
    def api(self) -> WithingsApi:
        """Get the api object."""
        return self._api

    @property
    def measures(self) -> MeasureGetMeasResponse:
        """Get the current measures data."""
        return self._measures

    @property
    def sleep(self) -> SleepGetResponse:
        """Get the current sleep data."""
        return self._sleep

    @property
    def sleep_summary(self) -> SleepGetSummaryResponse:
        """Get the current sleep summary data."""
        return self._sleep_summary

    @staticmethod
    def get_throttle_interval() -> int:
        """Get the throttle interval."""
        return const.THROTTLE_INTERVAL

    def get_throttle_data(self, domain: str) -> ThrottleData:
        """Get throttlel data."""
        return self.throttle_data.get(domain)

    def set_throttle_data(self, domain: str, throttle_data: ThrottleData):
        """Set throttle data."""
        self.throttle_data[domain] = throttle_data

    @staticmethod
    def print_service_unavailable() -> bool:
        """Print the service is unavailable (once) to the log."""
        if WithingsDataManager.service_available is not False:
            _LOGGER.error("Looks like the service is not available at the moment")
            WithingsDataManager.service_available = False
            return True

        return False

    @staticmethod
    def print_service_available() -> bool:
        """Print the service is available (once) to to the log."""
        if WithingsDataManager.service_available is not True:
            _LOGGER.info("Looks like the service is available again")
            WithingsDataManager.service_available = True
            return True

        return False

    async def call(self, function, throttle_domain=None) -> Any:
        """Call an api method and handle the result."""
        throttle_data = self.get_throttle_data(throttle_domain)

        should_throttle = (
            throttle_domain and throttle_data and not throttle_data.is_expired()
        )

        try:
            if should_throttle:
                _LOGGER.debug("Throttling call for domain: %s", throttle_domain)
                result = throttle_data.data
            else:
                _LOGGER.debug("Running call.")
                result = await self._hass.async_add_executor_job(function)

                # Update throttle data.
                self.set_throttle_data(
                    throttle_domain, ThrottleData(self.get_throttle_interval(), result)
                )

            WithingsDataManager.print_service_available()
            return result

        except MissingTokenError as ex:
            raise NotAuthenticatedError(ex)

        except Exception as ex:  # pylint: disable=broad-except
            # Service error, probably not authenticated.
            if NOT_AUTHENTICATED_ERROR.match(str(ex)):
                raise NotAuthenticatedError(ex)

            # Probably a network error.
            WithingsDataManager.print_service_unavailable()
            raise PlatformNotReady(ex)

    async def check_authenticated(self) -> bool:
        """Check if the user is authenticated."""
        def function():
            return bool(self._api.user_get_device())

        return await self.call(function)

    async def update_measures(self) -> MeasureGetMeasResponse:
        """Update the measures data."""
        def function():
            return self._api.measure_get_meas()

        self._measures = await self.call(function, throttle_domain="update_measures")

        return self._measures

    async def update_sleep(self) -> SleepGetResponse:
        """Update the sleep data."""
        end_date = int(time.time())
        start_date = end_date - (6 * 60 * 60)

        def function():
            return self._api.sleep_get(startdate=start_date, enddate=end_date)

        self._sleep = await self.call(function, throttle_domain="update_sleep")

        return self._sleep

    async def update_sleep_summary(self) -> SleepGetSummaryResponse:
        """Update the sleep summary data."""
        now = dt.utcnow()
        yesterday = now - datetime.timedelta(days=1)
        yesterday_noon = datetime.datetime(
            yesterday.year,
            yesterday.month,
            yesterday.day,
            12,
            0,
            0,
            0,
            datetime.timezone.utc,
        )

        _LOGGER.debug(
            "Getting sleep summary data since: %s",
            yesterday.strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

        def function():
            return self._api.sleep_get_summary(lastupdate=yesterday_noon)

        self._sleep_summary = await self.call(
            function, throttle_domain="update_sleep_summary"
        )

        return self._sleep_summary


def create_withings_data_manager(
    hass: HomeAssistantType, entry: ConfigEntry
) -> WithingsDataManager:
    """Set up the sensor config entry."""
    entry_creds = entry.data.get(const.CREDENTIALS) or {}
    profile = entry.data[const.PROFILE]
    credentials = Credentials(
        access_token=entry_creds.get("access_token"),
        token_expiry=entry_creds.get("token_expiry"),
        token_type=entry_creds.get("token_type"),
        refresh_token=entry_creds.get("refresh_token"),
        userid=entry_creds.get("userid") or entry_creds.get("user_id"),
        client_id=entry_creds.get("client_id"),
        consumer_secret=entry_creds.get("consumer_secret"),
    )

    def credentials_saver(credentials_param: Credentials):
        _LOGGER.debug("Saving updated credentials of type %s", type(credentials_param))
        entry.data[const.CREDENTIALS] = credentials_param._asdict()
        hass.config_entries.async_update_entry(entry, data={**entry.data})

    _LOGGER.debug("Creating withings api instance")
    api = WithingsApi(credentials=credentials, refresh_cb=credentials_saver)

    _LOGGER.debug("Creating withings data manager for profile: %s", profile)
    return WithingsDataManager(hass, profile, api)


def get_data_manager(
    hass: HomeAssistantType, entry: ConfigEntry
) -> WithingsDataManager:
    """Get a data manager for a config entry.

    If the data manager doesn't exist yet, it will be
    created and cached for later use.
    """
    profile = entry.data.get(const.PROFILE)

    hass.data[const.DOMAIN] = hass.data.get(const.DOMAIN, {})

    domain_dict = hass.data[const.DOMAIN]
    domain_dict[const.DATA_MANAGER] = domain_dict.get(const.DATA_MANAGER, {})

    dm_dict = domain_dict[const.DATA_MANAGER]
    dm_dict[profile] = dm_dict.get(profile, create_withings_data_manager(hass, entry))

    return dm_dict[profile]
