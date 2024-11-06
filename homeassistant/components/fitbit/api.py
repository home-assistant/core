"""API for fitbit bound to Home Assistant OAuth."""

from abc import ABC, abstractmethod
from collections.abc import Callable
import logging
from typing import Any, cast

from fitbit import Fitbit
from fitbit.exceptions import HTTPException, HTTPUnauthorized
from requests.exceptions import ConnectionError as RequestsConnectionError

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import FitbitUnitSystem
from .exceptions import FitbitApiException, FitbitAuthException
from .model import FitbitDevice, FitbitProfile

_LOGGER = logging.getLogger(__name__)

CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES_AT = "expires_at"


class FitbitApi(ABC):
    """Fitbit client library wrapper base class.

    This can be subclassed with different implementations for providing an access
    token depending on the use case.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        unit_system: FitbitUnitSystem | None = None,
    ) -> None:
        """Initialize Fitbit auth."""
        self._hass = hass
        self._profile: FitbitProfile | None = None
        self._unit_system = unit_system

    @abstractmethod
    async def async_get_access_token(self) -> dict[str, Any]:
        """Return a valid token dictionary for the Fitbit API."""

    async def _async_get_client(self) -> Fitbit:
        """Get synchronous client library, called before each client request."""
        # Always rely on Home Assistant's token update mechanism which refreshes
        # the data in the configuration entry.
        token = await self.async_get_access_token()
        return Fitbit(
            client_id=None,
            client_secret=None,
            access_token=token[CONF_ACCESS_TOKEN],
            refresh_token=token[CONF_REFRESH_TOKEN],
            expires_at=float(token[CONF_EXPIRES_AT]),
        )

    async def async_get_user_profile(self) -> FitbitProfile:
        """Return the user profile from the API."""
        if self._profile is None:
            client = await self._async_get_client()
            response: dict[str, Any] = await self._run(client.user_profile_get)
            _LOGGER.debug("user_profile_get=%s", response)
            profile = response["user"]
            self._profile = FitbitProfile(
                encoded_id=profile["encodedId"],
                display_name=profile["displayName"],
                locale=profile.get("locale"),
            )
        return self._profile

    async def async_get_unit_system(self) -> FitbitUnitSystem:
        """Get the unit system to use when fetching timeseries.

        This is used in a couple ways. The first is to determine the request
        header to use when talking to the fitbit API which changes the
        units returned by the API. The second is to tell Home Assistant the
        units set in sensor values for the values returned by the API.
        """
        if (
            self._unit_system is not None
            and self._unit_system != FitbitUnitSystem.LEGACY_DEFAULT
        ):
            return self._unit_system
        # Use units consistent with the account user profile or fallback to the
        # home assistant unit settings.
        profile = await self.async_get_user_profile()
        if profile.locale == FitbitUnitSystem.EN_GB:
            return FitbitUnitSystem.EN_GB
        if self._hass.config.units is METRIC_SYSTEM:
            return FitbitUnitSystem.METRIC
        return FitbitUnitSystem.EN_US

    async def async_get_devices(self) -> list[FitbitDevice]:
        """Return available devices."""
        client = await self._async_get_client()
        devices: list[dict[str, str]] = await self._run(client.get_devices)
        _LOGGER.debug("get_devices=%s", devices)
        return [
            FitbitDevice(
                id=device["id"],
                device_version=device["deviceVersion"],
                battery_level=int(device["batteryLevel"]),
                battery=device["battery"],
                type=device["type"],
            )
            for device in devices
        ]

    async def async_get_latest_time_series(self, resource_type: str) -> dict[str, Any]:
        """Return the most recent value from the time series for the specified resource type."""
        client = await self._async_get_client()

        # Set request header based on the configured unit system
        client.system = await self.async_get_unit_system()

        def _time_series() -> dict[str, Any]:
            return cast(dict[str, Any], client.time_series(resource_type, period="7d"))

        response: dict[str, Any] = await self._run(_time_series)
        _LOGGER.debug("time_series(%s)=%s", resource_type, response)
        key = resource_type.replace("/", "-")
        dated_results: list[dict[str, Any]] = response[key]
        return dated_results[-1]

    async def _run[_T](self, func: Callable[[], _T]) -> _T:
        """Run client command."""
        try:
            return await self._hass.async_add_executor_job(func)
        except RequestsConnectionError as err:
            _LOGGER.debug("Connection error to fitbit API: %s", err)
            raise FitbitApiException("Connection error to fitbit API") from err
        except HTTPUnauthorized as err:
            _LOGGER.debug("Unauthorized error from fitbit API: %s", err)
            raise FitbitAuthException("Authentication error from fitbit API") from err
        except HTTPException as err:
            _LOGGER.debug("Error from fitbit API: %s", err)
            raise FitbitApiException("Error from fitbit API") from err


class OAuthFitbitApi(FitbitApi):
    """Provide fitbit authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        unit_system: FitbitUnitSystem | None = None,
    ) -> None:
        """Initialize OAuthFitbitApi."""
        super().__init__(hass, unit_system)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> dict[str, Any]:
        """Return a valid access token for the Fitbit API."""
        await self._oauth_session.async_ensure_token_valid()
        return self._oauth_session.token


class ConfigFlowFitbitApi(FitbitApi):
    """Profile fitbit authentication before a ConfigEntry exists.

    This implementation directly provides the token without supporting refresh.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        token: dict[str, Any],
    ) -> None:
        """Initialize ConfigFlowFitbitApi."""
        super().__init__(hass)
        self._token = token

    async def async_get_access_token(self) -> dict[str, Any]:
        """Return the token for the Fitbit API."""
        return self._token
