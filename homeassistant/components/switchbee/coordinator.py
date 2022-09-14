"""SwitchBee integration Coordinator."""

from datetime import timedelta
import logging

from switchbee.api import CentralUnitAPI, SwitchBeeError
from switchbee.device import DeviceType, SwitchBeeBaseDevice

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SwitchBeeCoordinator(DataUpdateCoordinator[dict[int, SwitchBeeBaseDevice]]):
    """Class to manage fetching Freedompro data API."""

    def __init__(
        self,
        hass: HomeAssistant,
        swb_api: CentralUnitAPI,
        scan_interval: int,
    ) -> None:
        """Initialize."""
        self._api: CentralUnitAPI = swb_api
        self._reconnect_counts: int = 0
        self._mac_addr_fmt: str = format_mac(swb_api.mac)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    @property
    def api(self) -> CentralUnitAPI:
        """Return SwitchBee API object."""
        return self._api

    @property
    def mac_formated(self) -> str:
        """Return formatted MAC address."""
        return self._mac_addr_fmt

    async def _async_update_data(self) -> dict[int, SwitchBeeBaseDevice]:
        """Update data via library."""

        if self._reconnect_counts != self._api.reconnect_count:
            self._reconnect_counts = self._api.reconnect_count
            _LOGGER.debug(
                "Central Unit re-connected again due to invalid token, total %i",
                self._reconnect_counts,
            )

        # The devices are loaded once during the config_entry
        if not self._api.devices:
            # Try to load the devices from the CU for the first time
            try:
                await self._api.fetch_configuration(
                    [
                        DeviceType.Switch,
                        DeviceType.TimedSwitch,
                        DeviceType.GroupSwitch,
                        DeviceType.TimedPowerSwitch,
                    ]
                )
            except SwitchBeeError as exp:
                raise UpdateFailed(
                    f"Error communicating with API: {exp}"
                ) from SwitchBeeError
            else:
                _LOGGER.debug("Loaded devices")

        # Get the state of the devices
        try:
            await self._api.fetch_states()
        except SwitchBeeError as exp:
            raise UpdateFailed(
                f"Error communicating with API: {exp}"
            ) from SwitchBeeError
        else:
            return self._api.devices
