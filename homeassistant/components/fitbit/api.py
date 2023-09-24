"""API for fitbit bound to Home Assistant OAuth."""

import logging
from typing import Any

from fitbit import Fitbit

from homeassistant.core import HomeAssistant

from .model import FitbitDevice, FitbitProfile

_LOGGER = logging.getLogger(__name__)


class FitbitApi:
    """Fitbit client library wrapper base class."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Fitbit,
    ) -> None:
        """Initialize Fitbit auth."""
        self._hass = hass
        self._profile: FitbitProfile | None = None
        self._client = client

    @property
    def client(self) -> Fitbit:
        """Property to expose the underlying client library."""
        return self._client

    def get_user_profile(self) -> FitbitProfile:
        """Return the user profile from the API."""
        response: dict[str, Any] = self._client.user_profile_get()
        _LOGGER.debug("user_profile_get=%s", response)
        profile = response["user"]
        return FitbitProfile(
            encoded_id=profile["encodedId"],
            full_name=profile["fullName"],
            locale=profile.get("locale"),
        )

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
        response: dict[str, Any] = self._client.time_series(resource_type, period="7d")
        _LOGGER.debug("time_series(%s)=%s", resource_type, response)
        key = resource_type.replace("/", "-")
        dated_results: list[dict[str, Any]] = response[key]
        return dated_results[-1]
