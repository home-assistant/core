"""Define an object to manage fetching AirGradient data."""

from asyncio import sleep
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import timedelta
from typing import override

from airgradient import (
    AirGradientClient,
    AirGradientError,
    ApiVersion,
    Config,
    Measures,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type AirGradientConfigEntry = ConfigEntry[AirGradientCoordinator]

# V1 needs up to two seconds before GET reflects a successful PUT.
V1_CONFIG_APPLY_DELAY = 2


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
        # A V1 PUT can succeed before GET exposes the persisted config.
        # Track writes to avoid publishing a pre-write config response.
        self._config_write_generation = 0
        self._pending_config_writes = 0
        self._config_refresh_pending = False

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            measures = await self.client.get_current_measures()
        except AirGradientError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(error)},
            ) from error
        self._validate_measures_identity(measures)
        self._current_version = measures.firmware_version

    def _validate_measures_identity(self, measures: Measures) -> None:
        """Validate that measures are from the configured device."""
        if measures.serial_number != self.serial_number:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="identity_error",
                translation_placeholders={
                    "expected_serial_number": self.serial_number,
                    "serial_number": measures.serial_number,
                },
            )

    async def async_execute_config_write(self, write: Awaitable[None]) -> None:
        """Write config and refresh once V1 writes have settled."""
        if self.client.api_version is not ApiVersion.V1:
            await write
            await self.async_request_refresh()
            return

        self._pending_config_writes += 1
        try:
            await write
            self._config_write_generation += 1
            self._config_refresh_pending = True
            await sleep(V1_CONFIG_APPLY_DELAY)
        finally:
            self._pending_config_writes -= 1
            # Refresh accepted writes even if the final overlapping write failed.
            if not self._pending_config_writes and self._config_refresh_pending:
                self._config_refresh_pending = False
                await self.async_refresh()

    @override
    async def _async_update_data(self) -> AirGradientData:
        try:
            measures = await self.client.get_current_measures()
            self._validate_measures_identity(measures)
            if self.client.api_version is ApiVersion.V1:
                # PUT succeeds before GET reflects persisted config; retain the last
                # confirmed config while writes settle or race this GET.
                generation = self._config_write_generation
                if self._pending_config_writes:
                    config = self.data.config
                else:
                    config = await self.client.get_config()
                    if generation != self._config_write_generation:
                        config = self.data.config
            else:
                config = await self.client.get_config()
        except AirGradientError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(error)},
            ) from error
        if measures.firmware_version != self._current_version:
            device_registry = dr.async_get(self.hass)
            device_entry = device_registry.async_get_device_by_identifier(
                (DOMAIN, self.serial_number), self.config_entry.entry_id
            )
            assert device_entry
            device_registry.async_update_device(
                device_entry.id,
                sw_version=measures.firmware_version,
            )
            self._current_version = measures.firmware_version
        return AirGradientData(measures, config)
