"""Coordinator for Watergate API."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from watergate_local_api import WatergateApiException, WatergateLocalApiClient
from watergate_local_api.models import (
    AutoShutOffState,
    DeviceState,
    DeviceStateV2,
    NetworkingData,
    TelemetryData,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _as_device_state_v2(state: DeviceState | None) -> DeviceStateV2 | None:
    """Present a v1 device state as v2.

    Firmware without device state v2 reports a single water meter holding the difference
    between the positive and negative readings, so it is surfaced as the positive one and
    the negative one is left unset.
    """
    if state is None:
        return None
    return DeviceStateV2(
        valve_state=state.valve_state,
        water_flow_indicator=state.water_flow_indicator,
        mqtt_status=state.mqtt_status,
        wifi_status=state.wifi_status,
        power_supply=state.power_supply,
        firmware_version=state.firmware_version,
        uptime=state.uptime,
        water_meter_positive=state.water_meter,
        water_meter_negative=None,
        serial_number=state.serial_number,
    )


@dataclass
class WatergateAgregatedRequests:
    """Class to hold aggregated requests."""

    state: DeviceStateV2
    telemetry: TelemetryData
    networking: NetworkingData
    auto_shut_off: AutoShutOffState


type WatergateConfigEntry = ConfigEntry[WatergateDataCoordinator]


class WatergateDataCoordinator(DataUpdateCoordinator[WatergateAgregatedRequests]):
    """Class to manage fetching watergate data."""

    config_entry: WatergateConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WatergateConfigEntry,
        api: WatergateLocalApiClient,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=2),
        )
        self.api = api
        self._supports_state_v2 = True
        self._state_v2_confirmed = False

    @override
    async def _async_update_data(self) -> WatergateAgregatedRequests:
        try:
            state = await self._async_fetch_device_state()
            telemetry = await self.api.async_get_telemetry_data()
            networking = await self.api.async_get_networking()
            auto_shut_off = await self.api.async_get_auto_shut_off()
        except WatergateApiException as exc:
            raise UpdateFailed(f"Sonic device is unavailable: {exc}") from exc
        if TYPE_CHECKING:
            # Every supported Sonic firmware reports auto shut-off; the client
            # raises rather than returning None when the read genuinely fails.
            assert auto_shut_off is not None
        return WatergateAgregatedRequests(state, telemetry, networking, auto_shut_off)

    async def _async_fetch_device_state(self) -> DeviceStateV2 | None:
        """Fetch the device state, preferring v2 and falling back to v1."""
        if not self._supports_state_v2:
            return _as_device_state_v2(await self.api.async_get_device_state())
        try:
            state_v2 = await self.api.async_get_device_state_v2()
        except WatergateApiException:
            if self._state_v2_confirmed:
                # v2 has been read before, so this is a transient failure, not old
                # firmware: keep the last data rather than switching the meter source.
                raise
            # The client reports a rejected media type and an unreachable device the same
            # way, so only a successful v1 read proves the firmware simply lacks v2. The
            # device may have come back in between, so v2 is tried once more before the
            # downgrade is made permanent.
            state = await self.api.async_get_device_state()
            try:
                state_v2 = await self.api.async_get_device_state_v2()
            except WatergateApiException:
                self._supports_state_v2 = False
                _LOGGER.debug("Device state v2 is not supported, falling back to v1")
                return _as_device_state_v2(state)
        self._state_v2_confirmed = True
        return state_v2

    @override
    def async_set_updated_data(self, data: WatergateAgregatedRequests) -> None:
        """Manually update data, notify listeners and DO NOT reset refresh interval."""

        self.data = data
        self.logger.debug(
            "Manually updated %s data",
            self.name,
        )

        self.async_update_listeners()
