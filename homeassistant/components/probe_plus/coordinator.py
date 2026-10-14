"""Coordinator for the probe_plus integration."""

from collections.abc import Callable, Iterable
from datetime import timedelta
import logging
from typing import override

from pyprobeplus import ProbePlusDevice
from pyprobeplus.exceptions import ProbePlusDeviceNotFound, ProbePlusError

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

type ProbePlusConfigEntry = ConfigEntry[ProbePlusDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=15)


class ProbePlusDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to manage data updates for a probe device.

    This class handles the communication with Probe Plus devices.

    Data is updated by the device itself.
    """

    config_entry: ProbePlusConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ProbePlusConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ProbePlusDataUpdateCoordinator",
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )

        available_scanners = bluetooth.async_scanner_count(hass, connectable=True)

        if available_scanners == 0:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="no_bleak_scanner",
            )

        self.device: ProbePlusDevice = ProbePlusDevice(
            address_or_ble_device=entry.data[CONF_ADDRESS],
            scanner=bluetooth.async_get_scanner(hass),
            name=entry.title,
            notify_callback=self.async_update_listeners,
        )

    @override
    async def _async_update_data(self) -> None:
        """Connect to the Probe Plus device on a set interval.

        This method is called periodically to reconnect to the device
        Data updates are handled by the device itself.
        """
        # Already connected, no need to update any data as the device streams this.
        if self.device.connected:
            return

        # Probe is not connected, try to connect
        try:
            await self.device.connect()
        except (ProbePlusError, ProbePlusDeviceNotFound, TimeoutError) as e:
            _LOGGER.debug(
                "Could not connect to scale: %s, Error: %s",
                self.config_entry.data[CONF_ADDRESS],
                e,
            )
            self.device.device_disconnected_handler(notify=False)
            return

    @callback
    def setup_dynamic_discovery(
        self,
        entry: ProbePlusConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
        entity_fn: Callable[[int], Iterable[Entity]],
    ) -> None:
        """Set up dynamic discovery of entities for the probe device."""
        known_slots: set[int] = set()

        @callback
        def _maybe_add_entities() -> None:
            """Check/add entities when a new probe is detected."""
            for slot, _ in enumerate(self.device.device_state.probes):
                if slot not in known_slots:
                    known_slots.add(slot)
                    async_add_entities(entity_fn(slot))

        entry.async_on_unload(self.async_add_listener(_maybe_add_entities))
        _maybe_add_entities()
