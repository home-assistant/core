"""SwitchBee integration Coordinator."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging

from switchbee.api import CentralUnitPolling, CentralUnitWsRPC
from switchbee.api.central_unit import SwitchBeeError
from switchbee.device import DeviceType, SwitchBeeBaseDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL_SEC

_LOGGER = logging.getLogger(__name__)


class SwitchBeeCoordinator(DataUpdateCoordinator[Mapping[int, SwitchBeeBaseDevice]]):
    """Class to manage fetching SwitchBee data API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        swb_api: CentralUnitPolling | CentralUnitWsRPC,
    ) -> None:
        """Initialize."""
        self.api: CentralUnitPolling | CentralUnitWsRPC = swb_api
        self._reconnect_counts: int = 0
        assert self.api.mac is not None
        self.unique_id = (
            self.api.unique_id
            if self.api.unique_id is not None
            else format_mac(self.api.mac)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SEC[type(self.api)]),
        )

        # Register callback for notification WsRPC
        if isinstance(self.api, CentralUnitWsRPC):
            self.api.subscribe_updates(self._async_handle_update)

    @callback
    def _async_handle_update(self, push_data: dict) -> None:
        """Manually update data and notify listeners."""
        assert isinstance(self.api, CentralUnitWsRPC)
        _LOGGER.debug("Received update: %s", push_data)
        self.async_set_updated_data(self.api.devices)

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
                        DeviceType.VRFAC,
                    ]
                )
            except SwitchBeeError as exp:
                raise UpdateFailed(
                    f"Error communicating with API: {exp}"
                ) from SwitchBeeError

            _LOGGER.debug("Loaded devices")

        # Get the state of the devices
        try:
            await self.api.fetch_states()
        except SwitchBeeError as exp:
            raise UpdateFailed(
                f"Error communicating with API: {exp}"
            ) from SwitchBeeError

        return self.api.devices
