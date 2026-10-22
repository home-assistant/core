"""Coordinator for the KACO RS485 integration."""

from datetime import timedelta
from typing import override

from kaco_rs485 import AsyncBus, BusError, InverterState, KacoRs485Client, status_text

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ADDRESSES, DOMAIN, LOGGER

SCAN_INTERVAL = timedelta(seconds=30)

type KacoRs485ConfigEntry = ConfigEntry[KacoRs485Coordinator]


class KacoRs485Coordinator(DataUpdateCoordinator[dict[int, InverterState]]):
    """Runs one poll cycle per interval over a single long-lived connection."""

    config_entry: KacoRs485ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: KacoRs485ConfigEntry,
        port: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )
        self._bus = AsyncBus(port)
        self._addresses: list[int] = []
        self._client = KacoRs485Client(self._bus, [])
        self._opened = False
        self._reported_dark: dict[int, bool] = {}

    def _enabled_addresses(self) -> list[int]:
        """Return the addresses whose device has not been disabled.

        Disabled inverters are not polled, so they cost no bus time.
        """
        registry = dr.async_get(self.hass)
        return [
            address
            for address in self.config_entry.data[CONF_ADDRESSES]
            if (
                device := registry.async_get_device_by_identifier(
                    (DOMAIN, f"{self.config_entry.entry_id}_{address}"),
                    self.config_entry.entry_id,
                )
            )
            is None
            or not device.disabled
        ]

    async def _async_open(self) -> None:
        """Open the bus."""
        await self._bus.open()
        self._opened = True

    async def async_close(self) -> None:
        """Close the bus if it is open."""
        if self._opened:
            await self._bus.close()
            self._opened = False

    @override
    async def _async_update_data(self) -> dict[int, InverterState]:
        if (addresses := self._enabled_addresses()) != self._addresses:
            self._addresses = addresses
            self._client = KacoRs485Client(self._bus, addresses)

        if not self._addresses:
            return {}

        # A proxy can vanish and take the port with it; reopen instead.
        if not self._opened:
            try:
                await self._async_open()
            except BusError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="cannot_open_port",
                    translation_placeholders={"error": str(err)},
                ) from err

        try:
            states = await self._client.poll_cycle()
        except BusError as err:
            await self.async_close()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="bus_error",
                translation_placeholders={"error": str(err)},
            ) from err

        self._log_availability(states)
        return states

    def _log_availability(self, states: dict[int, InverterState]) -> None:
        """Log once per inverter going dark, and once on its return."""
        for address, state in states.items():
            dark = not state.available
            if dark == self._reported_dark.get(address, False):
                continue
            self._reported_dark[address] = dark

            if not dark:
                LOGGER.info("Inverter %d is answering again", address)
            elif state.measured is not None:
                LOGGER.info(
                    "Inverter %d stopped answering, last reported %s",
                    address,
                    status_text(state.measured.status),
                )
            else:
                LOGGER.info("Inverter %d stopped answering", address)
