"""API for fitbit bound to Home Assistant OAuth."""

import logging
from typing import Any

from fitbit import Fitbit

from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import FitbitUnitSystem
from .model import FitbitDevice, FitbitProfile

_LOGGER = logging.getLogger(__name__)


class FitbitApi:
    """Fitbit client library wrapper base class."""

    def __init__(
        self, hass: HomeAssistant, client: Fitbit, unit_system: str | None = None
    ) -> None:
        """Initialize Fitbit auth."""
        self._hass = hass
        self._profile: FitbitProfile | None = None
        self._client = client
        self._unit_system = unit_system

    @property
    def client(self) -> Fitbit:
        """Property to expose the underlying client library."""
        return self._client

    def get_user_profile(self) -> FitbitProfile:
        """Return the user profile from the API."""
        if self._profile is None:
            response: dict[str, Any] = self._client.user_profile_get()
            _LOGGER.debug("user_profile_get=%s", response)
            profile = response["user"]
            self._profile = FitbitProfile(
                encoded_id=profile["encodedId"],
                full_name=profile["fullName"],
                locale=profile.get("locale"),
            )
        return self._profile

    def get_unit_system(self) -> str:
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
        profile = self.get_user_profile()
        if profile.locale == FitbitUnitSystem.EN_GB:
            return FitbitUnitSystem.EN_GB
        if self._hass.config.units is METRIC_SYSTEM:
            return FitbitUnitSystem.METRIC
        return FitbitUnitSystem.EN_US

    def get_devices(self) -> list[FitbitDevice]:
        """Return available devices."""
        devices: list[dict[str, str]] = self._client.get_devices()
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

    def get_latest_time_series(self, resource_type: str) -> dict[str, Any]:
        """Return the most recent value from the time series for the specified resource type."""

        # Set request header based on the configured unit system
        self._client.system = self.get_unit_system()

        response: dict[str, Any] = self._client.time_series(resource_type, period="7d")
        _LOGGER.debug("time_series(%s)=%s", resource_type, response)
        key = resource_type.replace("/", "-")
        dated_results: list[dict[str, Any]] = response[key]
        return dated_results[-1]
