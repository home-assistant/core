"""The data update coordinator for the A. O. Smith integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from py_aosmith import (
    AOSmithAPIClient,
    AOSmithInvalidCredentialsException,
    AOSmithUnknownException,
)
from py_aosmith.models import Device as AOSmithDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, ENERGY_USAGE_INTERVAL, FAST_INTERVAL, REGULAR_INTERVAL

_LOGGER = logging.getLogger(__name__)

type AOSmithConfigEntry = ConfigEntry[AOSmithData]


@dataclass
class AOSmithData:
    """Data for the A. O. Smith integration."""

    client: AOSmithAPIClient
    status_coordinator: AOSmithStatusCoordinator
    energy_coordinator: AOSmithEnergyCoordinator


class AOSmithStatusCoordinator(DataUpdateCoordinator[dict[str, AOSmithDevice]]):
    """Coordinator for device status, updating with a frequent interval."""

    config_entry: AOSmithConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AOSmithConfigEntry,
        client: AOSmithAPIClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=REGULAR_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, AOSmithDevice]:
        """Fetch latest data from the device status endpoint."""
        try:
            devices = await self.client.get_devices()
        except AOSmithInvalidCredentialsException as err:
            raise ConfigEntryAuthFailed from err
        except AOSmithUnknownException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        mode_pending = any(device.status.mode_change_pending for device in devices)
        setpoint_pending = any(
            device.status.temperature_setpoint_pending for device in devices
        )

        if mode_pending or setpoint_pending:
            self.update_interval = FAST_INTERVAL
        else:
            self.update_interval = REGULAR_INTERVAL

        return {device.junction_id: device for device in devices}


class AOSmithEnergyCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Coordinator for energy usage data, updating with a slower interval."""

    config_entry: AOSmithConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AOSmithConfigEntry,
        client: AOSmithAPIClient,
        junction_ids: list[str],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=ENERGY_USAGE_INTERVAL,
        )
        self.client = client
        self.junction_ids = junction_ids

    async def _async_update_data(self) -> dict[str, float]:
        """Fetch latest data from the energy usage endpoint."""
        energy_usage_by_junction_id: dict[str, float] = {}

        for junction_id in self.junction_ids:
            try:
                energy_usage = await self.client.get_energy_use_data(junction_id)
            except AOSmithInvalidCredentialsException as err:
                raise ConfigEntryAuthFailed from err
            except AOSmithUnknownException as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err

            energy_usage_by_junction_id[junction_id] = energy_usage.lifetime_kwh

        return energy_usage_by_junction_id
