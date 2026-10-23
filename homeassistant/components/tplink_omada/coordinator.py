"""Generic Omada API coordinator."""

import asyncio
from datetime import timedelta
import logging
import math
from typing import TYPE_CHECKING, NamedTuple, override

from tplink_omada_client import (
    OmadaClient,
    OmadaControllerStatus,
    OmadaControllerUpdateInfo,
    OmadaSiteClient,
    OmadaSwitchPortDetails,
)
from tplink_omada_client.clients import OmadaWirelessClient
from tplink_omada_client.devices import (
    OmadaFirmwareUpdate,
    OmadaGateway,
    OmadaListDevice,
    OmadaSwitch,
)
from tplink_omada_client.exceptions import OmadaClientException

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import OmadaConfigEntry
    from .controller import OmadaSiteController

_LOGGER = logging.getLogger(__name__)

POLL_SWITCH_PORT = 30
POLL_GATEWAY = 300
POLL_CLIENTS = 300
POLL_DEVICES = 300
POLL_CONTROLLER = 300
POLL_CONTROLLER_UPDATE = 3600
POLL_UPGRADE = 60

# Minimum number of consecutive empty device-list updates required before
# removing device entries, to tolerate transient empty responses from the
# controller. The window is one hour, scaled up when polling speeds up during
# a firmware download.
EMPTY_DEVICE_LIMIT = 12
EMPTY_DEVICE_WINDOW = 3600


class OmadaCoordinator[_T](DataUpdateCoordinator[dict[str, _T]]):
    """Coordinator for synchronizing bulk Omada data."""

    config_entry: OmadaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OmadaConfigEntry,
        omada_client: OmadaSiteClient,
        name: str,
        poll_delay: int | None = 300,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Omada API Data - {name}",
            update_interval=timedelta(seconds=poll_delay) if poll_delay else None,
        )
        self.omada_client = omada_client

    @override
    async def _async_update_data(self) -> dict[str, _T]:
        """Fetch data from API endpoint."""
        try:
            async with asyncio.timeout(10):
                return await self.poll_update()
        except OmadaClientException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err

    async def poll_update(self) -> dict[str, _T]:
        """Poll the current data from the controller."""
        raise NotImplementedError("Update method not implemented")


class OmadaControllerStatusCoordinator(DataUpdateCoordinator[OmadaControllerStatus]):
    """Coordinator for getting status information about the Omada Controller."""

    config_entry: OmadaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OmadaConfigEntry,
        omada_client: OmadaClient,
    ) -> None:
        """Initialize the controller status coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Omada API Data - Controller Status",
            update_interval=timedelta(seconds=POLL_CONTROLLER),
        )
        self.omada_client = omada_client

    @override
    async def _async_update_data(self) -> OmadaControllerStatus:
        """Fetch controller status from the API."""
        try:
            async with asyncio.timeout(10):
                return await self.omada_client.get_controller_status()
        except OmadaClientException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err


class OmadaControllerUpdateCoordinator(
    DataUpdateCoordinator[OmadaControllerUpdateInfo]
):
    """Coordinator for controller firmware update information."""

    config_entry: OmadaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OmadaConfigEntry,
        omada_client: OmadaClient,
    ) -> None:
        """Initialize the controller update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Omada API Data - Controller Firmware Update",
            update_interval=timedelta(seconds=POLL_CONTROLLER_UPDATE),
        )
        self.omada_client = omada_client

    @override
    async def _async_update_data(self) -> OmadaControllerUpdateInfo:
        """Fetch controller firmware update information from the API."""
        try:
            async with asyncio.timeout(10):
                return await self.omada_client.check_firmware_updates()
        except OmadaClientException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err


class OmadaSwitchPortCoordinator(OmadaCoordinator[OmadaSwitchPortDetails]):
    """Coordinator for getting details about ports on a switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OmadaConfigEntry,
        omada_client: OmadaSiteClient,
        network_switch: OmadaSwitch,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            config_entry,
            omada_client,
            f"{network_switch.name} Ports",
            POLL_SWITCH_PORT,
        )
        self._network_switch = network_switch

    @override
    async def poll_update(self) -> dict[str, OmadaSwitchPortDetails]:
        """Poll a switch's current state."""
        ports = await self.omada_client.get_switch_ports(self._network_switch)
        return {p.port_id: p for p in ports}


class OmadaGatewayCoordinator(OmadaCoordinator[OmadaGateway]):
    """Coordinator for getting details about the site's gateway."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OmadaConfigEntry,
        omada_client: OmadaSiteClient,
        mac: str,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(hass, config_entry, omada_client, "Gateway", POLL_GATEWAY)
        self.mac = mac

    def invalidate(self) -> None:
        """Drop cached gateway data so a returning gateway is refetched."""
        self.data = {}

    @override
    async def poll_update(self) -> dict[str, OmadaGateway]:
        """Poll a the gateway's current state."""
        gateway = await self.omada_client.get_gateway(self.mac)
        return {self.mac: gateway}


class OmadaDevicesCoordinator(OmadaCoordinator[OmadaListDevice]):
    """Coordinator for generic device lists from the controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OmadaConfigEntry,
        omada_client: OmadaSiteClient,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(hass, config_entry, omada_client, "DeviceList", POLL_CLIENTS)
        self.consecutive_empty_updates = 0

    @override
    async def _async_update_data(self) -> dict[str, OmadaListDevice]:
        """Fetch the device list and track consecutive empty responses."""
        try:
            devices = await super()._async_update_data()
        except Exception:
            # Any failed poll says nothing about the devices, so the empty
            # counter must not accumulate across it.
            self.consecutive_empty_updates = 0
            raise
        if devices:
            self.consecutive_empty_updates = 0
        else:
            self.consecutive_empty_updates += 1
        return devices

    @override
    async def poll_update(self) -> dict[str, OmadaListDevice]:
        """Poll the site's current registered Omada devices."""
        return {d.mac: d for d in await self.omada_client.get_devices()}


class OmadaClientsCoordinator(OmadaCoordinator[OmadaWirelessClient]):
    """Coordinator for getting details about the site's connected clients."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OmadaConfigEntry,
        omada_client: OmadaSiteClient,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(hass, config_entry, omada_client, "ClientsList", POLL_CLIENTS)

    @override
    async def poll_update(self) -> dict[str, OmadaWirelessClient]:
        """Poll the site's current active wi-fi clients."""
        return {
            c.mac: c
            async for c in self.omada_client.get_connected_clients()
            if isinstance(c, OmadaWirelessClient)
        }


class FirmwareUpdateStatus(NamedTuple):
    """Firmware update information for Omada SDN devices."""

    device: OmadaListDevice
    firmware: OmadaFirmwareUpdate | None


class OmadaFirmwareUpdateCoordinator(OmadaCoordinator[FirmwareUpdateStatus]):
    """Coordinator for Omada device firmware update details."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OmadaConfigEntry,
        omada_client: OmadaSiteClient,
        devices_coordinator: OmadaDevicesCoordinator,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass, config_entry, omada_client, "Firmware Updates", poll_delay=None
        )

        self._devices_coordinator = devices_coordinator
        self._config_entry = config_entry

        config_entry.async_on_unload(
            devices_coordinator.async_add_listener(self._handle_devices_update)
        )

    async def _get_firmware_updates(self) -> list[FirmwareUpdateStatus]:
        devices = self._devices_coordinator.data.values()

        updates = [
            FirmwareUpdateStatus(
                device=d,
                firmware=None
                if not d.need_upgrade
                else await self.omada_client.get_firmware_details(d),
            )
            for d in devices
        ]

        # During a firmware upgrade, poll device list more frequently
        self._devices_coordinator.update_interval = timedelta(
            seconds=(
                POLL_UPGRADE
                if any(u.device.fw_download for u in updates)
                else POLL_DEVICES
            )
        )
        return updates

    @override
    async def poll_update(self) -> dict[str, FirmwareUpdateStatus]:
        """Poll the state of Omada Devices firmware update availability."""
        return {d.device.mac: d for d in await self._get_firmware_updates()}

    @callback
    def _handle_devices_update(self) -> None:
        """Handle updated data from the devices coordinator."""
        # Trigger a refresh of our data, based on the updated device list
        self._config_entry.async_create_background_task(
            self.hass, self.async_request_refresh(), "Omada Firmware Update Refresh"
        )


def device_removal_is_confirmed(coordinator: OmadaDevicesCoordinator) -> bool:
    """Return True when the device list can be trusted for removal decisions."""
    if not coordinator.last_update_success:
        return False

    if coordinator.data:
        return True

    # A successful but empty response is likely a transient controller glitch,
    # and removal also deletes the device's entities from the registry, so only
    # clean once the empty list is confirmed over a full window of updates.
    # Polling runs faster during a firmware download, so scale the count.
    interval = coordinator.update_interval or timedelta(seconds=POLL_DEVICES)
    required = max(
        EMPTY_DEVICE_LIMIT,
        math.ceil(EMPTY_DEVICE_WINDOW / max(interval.total_seconds(), 1)),
    )
    return coordinator.consecutive_empty_updates >= required


async def async_cleanup_devices(
    hass: HomeAssistant,
    controller: OmadaSiteController,
) -> None:
    """Remove devices from the registry when Omada no longer reports them."""
    devices_coordinator = controller.devices_coordinator
    if not device_removal_is_confirmed(devices_coordinator):
        return

    devices = devices_coordinator.data
    device_registry = dr.async_get(hass)
    entry_id = devices_coordinator.config_entry.entry_id
    known_devices = {dr.format_mac(mac) for mac in devices}
    # The controller device is not part of the site's device list.
    controller_mac = dr.format_mac(controller.controller_status_coordinator.data.mac)

    for device_entry in dr.async_entries_for_config_entry(device_registry, entry_id):
        mac = next(
            (
                fmt
                for identifier in device_entry.identifiers
                if identifier[0] == DOMAIN
                and len(fmt := dr.format_mac(identifier[1])) == 17
                and fmt.count(":") == 5
            ),
            None,
        )

        if mac and mac not in known_devices and mac != controller_mac:
            _LOGGER.debug(
                "Removing stale Omada device %s from entry %s",
                mac,
                entry_id,
            )
            await controller.async_remove_device(mac, device_entry)
