"""Coordinator for the ZhongHong integration."""

from datetime import datetime
from typing import override

from zhong_hong_hvac.hub import ZhongHongGateway
from zhong_hong_hvac.hvac import HVAC as ZhongHongHVAC

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_GATEWAY_ADDRESS, DOMAIN, LOGGER, READBACK_DELAY, SCAN_INTERVAL

type ZhongHongConfigEntry = ConfigEntry[ZhongHongCoordinator]

type DeviceAddress = tuple[int, int]


def device_unique_id(entry: ZhongHongConfigEntry, address: DeviceAddress) -> str:
    """Return the unique ID of the air conditioner at an address."""
    return f"{entry.entry_id}_{address[0]}_{address[1]}"


def legacy_device_unique_id(address: DeviceAddress) -> str:
    """Return the identifier the YAML platform gave the air conditioner.

    It carried only the address on the bus, so two gateways with an air
    conditioner at the same address, which `(1, 1)` commonly is, produced the
    same one and the second entity was dropped. Entities are moved off it on
    setup; it is still needed to find them.
    """
    return f"zhong_hong_hvac_{address[0]}_{address[1]}"


class ZhongHongCoordinator(DataUpdateCoordinator[dict[DeviceAddress, ZhongHongHVAC]]):
    """Own the gateway connection and fan its pushes out to the entities.

    The gateway pushes state on its own socket, so this coordinator is mostly a
    dispatch point: the library calls back on its listener thread and we hand
    the devices to the entities from the event loop. Polling remains as a
    fallback for pushes missed while the connection was down.
    """

    config_entry: ZhongHongConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ZhongHongConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=config_entry.data[CONF_HOST],
            update_interval=SCAN_INTERVAL,
        )
        self.hub = ZhongHongGateway(
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_PORT],
            config_entry.data[CONF_GATEWAY_ADDRESS],
        )
        self.devices: dict[DeviceAddress, ZhongHongHVAC] = {}
        self._readback_cancel: CALLBACK_TYPE | None = None

    @override
    async def _async_setup(self) -> None:
        """Discover the devices behind the gateway and start listening.

        Discovery has to happen before the listener thread starts, because both
        read from the same socket.
        """
        try:
            addresses = await self.hass.async_add_executor_job(self.hub.discovery_ac)
        except OSError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"host": self.hub.ip_addr},
            ) from err

        if not addresses:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="no_devices_found",
                translation_placeholders={"host": self.hub.ip_addr},
            )

        # Creating the device registers it with the hub, which is what routes
        # the gateway's pushes to _handle_device_update below.
        self.devices = {
            address: ZhongHongHVAC(self.hub, *address) for address in addresses
        }
        for device in self.devices.values():
            device.register_update_callback(self._handle_device_update)

        await self.hass.async_add_executor_job(self.hub.start_listen)

    def schedule_readback(self) -> None:
        """Schedule a re-read from the executor the commands are sent on."""
        self.hass.loop.call_soon_threadsafe(self.async_schedule_readback)

    @callback
    def async_schedule_readback(self) -> None:
        """Re-read the gateway shortly after it has been commanded.

        A unit takes a second or three to act on a command, and the gateway
        pushes the new state once it has. That push is the only thing the
        state comes from, so if it goes missing the entity keeps showing what
        the unit was doing before, until the next poll a minute later. Asking
        again a few seconds in costs one round trip and closes that window.
        """
        if self._readback_cancel is not None:
            self._readback_cancel()

        async def _readback(_now: datetime) -> None:
            self._readback_cancel = None
            await self.async_request_refresh()

        self._readback_cancel = async_call_later(self.hass, READBACK_DELAY, _readback)

    def _handle_device_update(self, device: ZhongHongHVAC) -> None:
        """Handle a state push from the gateway.

        Called on the library's listener thread, so the update has to be handed
        back to the event loop before touching any coordinator state.
        """
        self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, self.devices)

    @override
    async def _async_update_data(self) -> dict[DeviceAddress, ZhongHongHVAC]:
        """Ask the gateway to re-send the state of every device."""
        if not self.hub.connected:
            raise UpdateFailed(f"Lost connection to the gateway at {self.hub.ip_addr}")

        if not await self.hass.async_add_executor_job(self.hub.query_all_status):
            raise UpdateFailed(f"Failed to query the gateway at {self.hub.ip_addr}")

        return self.devices

    @override
    async def async_shutdown(self) -> None:
        """Stop the listener thread and close the gateway socket."""
        if self._readback_cancel is not None:
            self._readback_cancel()
            self._readback_cancel = None

        await super().async_shutdown()
        await self.hass.async_add_executor_job(self.hub.stop_listen)
