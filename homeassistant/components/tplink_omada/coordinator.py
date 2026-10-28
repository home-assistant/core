"""Generic Omada API coordinator."""

import asyncio
from datetime import timedelta
import logging
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

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .config_flow import CONF_SITE
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
POLL_KNOWN_CLIENTS = 3600


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


class OmadaKnownClientsCoordinator(OmadaCoordinator[OmadaWirelessClient]):
    """Coordinator for getting details about all wireless clients known to the controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OmadaConfigEntry,
        omada_client: OmadaSiteClient,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            config_entry,
            omada_client,
            "KnownClientsList",
            POLL_KNOWN_CLIENTS,
        )

    @override
    async def _async_update_data(self) -> dict[str, OmadaWirelessClient]:
        """Fetch known clients and remove trackers the controller dropped."""
        clients = await super()._async_update_data()
        # An empty response is a controller glitch, not proof that every client
        # is gone; cleanup ignores it and keeps the trackers.
        cleanup_client_trackers(self.hass, self.config_entry.runtime_data, clients)
        return clients

    @override
    async def poll_update(self) -> dict[str, OmadaWirelessClient]:
        """Poll the site's all-time known wireless clients."""
        return {
            client.mac: client
            async for client in self.omada_client.get_known_clients()
            if isinstance(client, OmadaWirelessClient)
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


@callback
def cleanup_client_trackers(
    hass: HomeAssistant,
    controller: OmadaSiteController,
    known_clients: dict[str, OmadaWirelessClient] | None = None,
) -> None:
    """Remove tracker entities for clients missing from the controller list."""
    if known_clients is None:
        known_clients = controller.known_clients_coordinator.data or {}
    if not known_clients:
        return

    # Trackers are created as scanner_<site>_<client.mac>, with the MAC taken
    # from the same client list, so comparing unique IDs avoids parsing them.
    config_entry = controller.known_clients_coordinator.config_entry
    prefix = f"scanner_{config_entry.data[CONF_SITE]}_"
    known_unique_ids = {f"{prefix}{mac}" for mac in known_clients}
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    for entity in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        if entity.domain != DEVICE_TRACKER_DOMAIN:
            continue
        if not entity.unique_id.startswith(prefix):
            continue
        if entity.unique_id in known_unique_ids:
            continue
        if entity.disabled_by is not er.RegistryEntryDisabler.INTEGRATION:
            continue

        # The tracker has a device of its own, and removing the device also
        # removes the tracker. Keep a device that other entities share so they
        # are not detached.
        if (
            entity.device_id is not None
            and device_registry.async_get(entity.device_id) is not None
            and len(
                er.async_entries_for_device(
                    entity_registry,
                    entity.device_id,
                    include_disabled_entities=True,
                )
            )
            == 1
        ):
            device_registry.async_remove_device(entity.device_id)
            continue
        entity_registry.async_remove(entity.entity_id)
