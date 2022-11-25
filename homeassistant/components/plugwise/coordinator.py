"""DataUpdateCoordinator for Plugwise."""
from datetime import timedelta
from typing import NamedTuple, cast

from plugwise import Smile
from plugwise.constants import DeviceData, GatewayData
from plugwise.exceptions import (
    ConnectionFailedError,
    InvalidAuthentication,
    InvalidXMLError,
    ResponseError,
    UnsupportedDeviceError,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER


class PlugwiseData(NamedTuple):
    """Plugwise data stored in the DataUpdateCoordinator."""

    gateway: GatewayData
    devices: dict[str, DeviceData]


class PlugwiseDataUpdateCoordinator(DataUpdateCoordinator[PlugwiseData]):
    """Class to manage fetching Plugwise data from single endpoint."""

    def __init__(self, hass: HomeAssistant, api: Smile) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=api.smile_name or DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL.get(
                str(api.smile_type), timedelta(seconds=60)
            ),
            # Don't refresh immediately, give the device time to process
            # the change in state before we query it.
            request_refresh_debouncer=Debouncer(
                hass,
                LOGGER,
                cooldown=1.5,
                immediate=False,
            ),
        )
        self.api = api

    async def _async_update_data(self) -> PlugwiseData:
        """Fetch data from Plugwise."""
        try:
            data = await self.api.async_update()
        except InvalidAuthentication as err:
            raise UpdateFailed("Authentication failed") from err
        except (InvalidXMLError, ResponseError) as err:
            raise UpdateFailed(
                "Invalid XML data, or error indication received for the Plugwise Adam/Smile/Stretch"
            ) from err
        except UnsupportedDeviceError as err:
            raise UpdateFailed("Device with unsupported firmware") from err
        except ConnectionFailedError as err:
            raise UpdateFailed("Failed to connect") from err
        return PlugwiseData(
            gateway=cast(GatewayData, data[0]),
            devices=cast(dict[str, DeviceData], data[1]),
        )
