"""Rainforest data."""
from datetime import timedelta
import logging

from eagle200_reader import EagleReader
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from uEagle import Eagle as LegacyReader

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import TYPE_EAGLE_200, TYPE_LEGACY

_LOGGER = logging.getLogger(__name__)

UPDATE_ERRORS = (ConnectError, HTTPError, Timeout, ValueError)


class RainforestError(HomeAssistantError):
    """Base error."""


class CannotConnect(RainforestError):
    """Error to indicate a request failed."""


class InvalidAuth(RainforestError):
    """Error to indicate bad auth."""


def get_type(cloud_id, install_code):
    """Try API call 'get_network_info' to see if target device is Legacy or Eagle-200."""
    reader = FixedLegacyReader(cloud_id, install_code)

    try:
        response = reader.get_network_info()
    except UPDATE_ERRORS as error:
        _LOGGER.error("Failed to connect during setup: %s", error)
        raise CannotConnect from error

    # Branch to test if target is Legacy Model
    if (
        "NetworkInfo" in response
        and response["NetworkInfo"].get("ModelId") == "Z109-EAGLE"
    ):
        return TYPE_LEGACY

    # Branch to test if target is Eagle-200 Model
    if (
        "Response" in response
        and response["Response"].get("Command") == "get_network_info"
    ):
        return TYPE_EAGLE_200

    # Catch-all if hardware ID tests fail
    return None


class FixedLegacyReader(LegacyReader):
    """Wraps uEagle to make it behave like eagle_reader, offering update()."""

    def update(self):
        """Fetch and return the four sensor values in a dict."""
        out = {}

        resp = self.get_instantaneous_demand()["InstantaneousDemand"]
        out["instantanous_demand"] = resp["Demand"]

        resp = self.get_current_summation()["CurrentSummation"]
        out["summation_delivered"] = resp["SummationDelivered"]
        out["summation_received"] = resp["SummationReceived"]
        out["summation_total"] = out["summation_delivered"] - out["summation_received"]

        return out


class FixedEagleReader(EagleReader):
    """Wraps EagleReader to avoid updating in constructor."""

    # pylint: disable=super-init-not-called
    def __init__(self, ip_addr, cloud_id, install_code):
        """Initialize eagle reader.

        We don't call super() because it fetches data.
        """
        self.ip_addr = ip_addr
        self.cloud_id = cloud_id
        self.install_code = install_code

        self.instantanous_demand_value = 0.0
        self.summation_delivered_value = 0.0
        self.summation_received_value = 0.0
        self.summation_total_value = 0.0


class EagleDataCoordinator(DataUpdateCoordinator):
    """Get the latest data from the Eagle-200 device."""

    def __init__(self, hass, reader_type, cloud_id, install_code):
        """Initialize the data object."""
        super().__init__(
            hass, _LOGGER, name=cloud_id, update_interval=timedelta(seconds=30)
        )
        self.cloud_id = cloud_id
        if reader_type == TYPE_LEGACY:
            self._eagle_reader = FixedLegacyReader(cloud_id, install_code)
        else:
            self._eagle_reader = FixedEagleReader(
                f"eagle-{cloud_id}.local", cloud_id, install_code
            )

    async def _async_update_data(self):
        """Get the latest data from the Eagle-200 device."""
        try:
            data = await self.hass.async_add_executor_job(self._eagle_reader.update)
            _LOGGER.debug("API data: %s", data)
            return data
        except UPDATE_ERRORS as error:
            raise UpdateFailed from error
