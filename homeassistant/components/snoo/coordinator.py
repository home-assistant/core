"""Support for Snoo Coordinators."""

from datetime import timedelta
import logging

from python_snoo.baby import Baby
from python_snoo.containers import BabyData, SnooData, SnooDevice
from python_snoo.snoo import Snoo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

type SnooConfigEntry = ConfigEntry[dict[str, SnooCoordinator]]

_LOGGER = logging.getLogger(__name__)


class SnooCoordinator(DataUpdateCoordinator[SnooData]):
    """Snoo coordinator."""

    config_entry: SnooConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SnooConfigEntry,
        device: SnooDevice,
        snoo: Snoo,
    ) -> None:
        """Set up Snoo Coordinator."""
        super().__init__(
            hass,
            name=device.name,
            config_entry=entry,
            logger=_LOGGER,
        )
        self.device_unique_id = device.serialNumber
        self.device = device
        self.snoo = snoo
        self.baby_coordinators: dict[str, SnooBabyCoordinator] = {}

    async def setup(self) -> None:
        """Perform setup needed on every coordintaor creation."""
        self.snoo.start_subscribe(self.device, self.async_set_updated_data)
        # After we subscribe - get the status so that we have something to start with.
        # We only need to do this once. The device will auto update otherwise.
        await self.snoo.get_status(self.device)

        if self.device.babyIds:
            for baby_id in self.device.babyIds:
                baby = Baby(baby_id, self.snoo)
                # Do the initial load here so we can set the name
                baby_data = await baby.get_status()
                baby_coordinator = SnooBabyCoordinator(
                    self.hass, self.config_entry, self.device_unique_id, baby, baby_data
                )
                self.baby_coordinators[baby_id] = baby_coordinator


class SnooBabyCoordinator(DataUpdateCoordinator[BabyData]):
    """Snoo baby coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SnooConfigEntry,
        snoo_unique_id: str,
        baby: Baby,
        baby_data: BabyData,
        update_interval: timedelta | None = None,
    ) -> None:
        """Set up Snoo Baby Coordinator."""
        if update_interval is None:
            update_interval = timedelta(minutes=5)

        super().__init__(
            hass,
            name=f"Baby - {baby_data.babyName}",
            config_entry=entry,
            update_interval=update_interval,
            logger=_LOGGER,
        )

        self.snoo_unique_id = snoo_unique_id
        self.baby = baby
        self.data = baby_data

    async def _async_update_data(self) -> None:
        """Fetch baby data."""
        status = await self.baby.get_status()
        self.data = status
