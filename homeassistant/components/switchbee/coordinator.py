"""SwitchBee integration Coordinator."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging

from switchbee.api import CentralUnitAPI, SwitchBeeError
from switchbee.device import DeviceType, SwitchBeeBaseDevice

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL_SEC

_LOGGER = logging.getLogger(__name__)


class SwitchBeeCoordinator(DataUpdateCoordinator[Mapping[int, SwitchBeeBaseDevice]]):
    """Class to manage fetching Freedompro data API."""

    def __init__(
        self,
        hass: HomeAssistant,
        swb_api: CentralUnitAPI,
    ) -> None:
        """Initialize."""
        self.api: CentralUnitAPI = swb_api
        self._reconnect_counts: int = 0
        self.mac_formatted: str | None = (
            None if self.api.mac is None else format_mac(self.api.mac)
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SEC),
        )

    async def _async_update_data(self) -> Mapping[int, SwitchBeeBaseDevice]:
        """Update data via library."""

        if self._reconnect_counts != self.api.reconnect_count:
            self._reconnect_counts = self.api.reconnect_count
            _LOGGER.debug(
                "Central Unit re-connected again due to invalid token, total %i",
                self._reconnect_counts,
            )

        # The devices are loaded once during the config_entry
        if not self.api.devices:
            # Try to load the devices from the CU for the first time
            try:
                await self.api.fetch_configuration(
                    [
                        DeviceType.Switch,
                        DeviceType.TimedSwitch,
                        DeviceType.GroupSwitch,
                        DeviceType.TimedPowerSwitch,
                        DeviceType.Scenario,
                        DeviceType.Dimmer,
                        DeviceType.Shutter,
                        DeviceType.Somfy,
                        DeviceType.Thermostat,
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
            await self.api.fetch_states()
        except SwitchBeeError as exp:
            raise UpdateFailed(
                f"Error communicating with API: {exp}"
            ) from SwitchBeeError

        return self.api.devices
