"""Define an object to manage fetching AirGradient data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from airgradient import AirGradientClient, AirGradientError, Config, Measures

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type AirGradientConfigEntry = ConfigEntry[AirGradientCoordinator]


@dataclass
class AirGradientData:
    """Class for AirGradient data."""

    measures: Measures
    config: Config


class AirGradientCoordinator(DataUpdateCoordinator[AirGradientData]):
    """Class to manage fetching AirGradient data."""

    config_entry: AirGradientConfigEntry
    _current_version: str

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AirGradientConfigEntry,
        client: AirGradientClient,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=f"AirGradient {client.host}",
            update_interval=timedelta(minutes=1),
        )
        self.client = client
        assert self.config_entry.unique_id
        self.serial_number = self.config_entry.unique_id

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        self._current_version = (
            await self.client.get_current_measures()
        ).firmware_version

    async def _async_update_data(self) -> AirGradientData:
        try:
            measures = await self.client.get_current_measures()
            config = await self.client.get_config()
        except AirGradientError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(error)},
            ) from error
        if measures.firmware_version != self._current_version:
            device_registry = dr.async_get(self.hass)
            device_entry = device_registry.async_get_device(
                identifiers={(DOMAIN, self.serial_number)}
            )
            assert device_entry
            device_registry.async_update_device(
                device_entry.id,
                sw_version=measures.firmware_version,
            )
            self._current_version = measures.firmware_version
        return AirGradientData(measures, config)
