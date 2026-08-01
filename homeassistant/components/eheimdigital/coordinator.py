"""Data update coordinator for the EHEIM Digital integration."""

import asyncio
from collections.abc import Callable
from typing import override

from aiohttp import ClientError
from eheimdigital.device import EheimDigitalDevice
from eheimdigital.hub import EheimDigitalHub
from eheimdigital.types import EheimDeviceType, EheimDigitalClientError, MsgTitle

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type AsyncSetupDeviceEntitiesCallback = Callable[
    [EheimDigitalDeviceUpdateCoordinator[EheimDigitalDevice]], None
]

type EheimDigitalConfigEntry = ConfigEntry[EheimDigitalUpdateCoordinator]


class EheimDigitalUpdateCoordinator(DataUpdateCoordinator[None]):
    """The EHEIM Digital main data update coordinator."""

    config_entry: EheimDigitalConfigEntry
    device_coordinators: dict[
        str, dict[MsgTitle, EheimDigitalDeviceUpdateCoordinator[EheimDigitalDevice]]
    ]
    main_device_added_event: asyncio.Event
    hub: EheimDigitalHub

    def __init__(
        self, hass: HomeAssistant, config_entry: EheimDigitalConfigEntry
    ) -> None:
        """Initialize the EHEIM Digital data update coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.main_device_added_event = asyncio.Event()
        self.hub = EheimDigitalHub(
            host=self.config_entry.data[CONF_HOST],
            session=async_get_clientsession(hass),
            loop=hass.loop,
            receive_callback=self._async_receive_callback,
            device_found_callback=self._async_device_found,
            main_device_added_event=self.main_device_added_event,
        )
        self.known_devices: set[str] = set()
        self.incomplete_devices: set[str] = set()
        self.platform_callbacks: set[AsyncSetupDeviceEntitiesCallback] = set()
        self.device_coordinators = {}

    def add_platform_callback(
        self,
        async_setup_device_entities: AsyncSetupDeviceEntitiesCallback,
    ) -> None:
        """Add the setup callbacks from a specific platform."""
        self.platform_callbacks.add(async_setup_device_entities)
        for device in self.device_coordinators.values():
            for coordinator in device.values():
                async_setup_device_entities(coordinator)

    async def _async_device_found(
        self, device_address: str, device_type: EheimDeviceType
    ) -> None:
        """Set up a new device found.

        This function is called from the library whenever a new device is added.
        """

        if self.hub.devices[device_address].is_missing_data:
            self.incomplete_devices.add(device_address)
            return

        if (
            device_address not in self.device_coordinators
            or device_address in self.incomplete_devices
        ):
            if device_address not in self.device_coordinators:
                self.device_coordinators[device_address] = {}
                for title in self.hub.devices[device_address].packet_mapping:
                    self.device_coordinators[device_address][title] = (
                        EheimDigitalDeviceUpdateCoordinator(
                            self.hass,
                            self.config_entry,
                            self,
                            self.hub.devices[device_address],
                            title,
                        )
                    )
                    for platform_callback in self.platform_callbacks:
                        platform_callback(
                            self.device_coordinators[device_address][title]
                        )
            if device_address in self.incomplete_devices:
                self.incomplete_devices.remove(device_address)

    async def _async_receive_callback(self, device: str, msg_title: MsgTitle) -> None:
        if any(self.incomplete_devices):
            for device_address in self.incomplete_devices.copy():
                if not self.hub.devices[device_address].is_missing_data:
                    await self._async_device_found(
                        device_address, EheimDeviceType.VERSION_UNDEFINED
                    )
        if (
            device in self.device_coordinators
            and msg_title in self.device_coordinators[device]
        ):
            self.device_coordinators[device][msg_title].async_set_updated_data(
                self.hub.devices[device]
            )

    @override
    async def _async_setup(self) -> None:
        try:
            await self.hub.connect()
            async with asyncio.timeout(2):
                # This event gets triggered when the first message is received from
                # the device, it contains the data necessary to create the main device.
                # This removes the race condition where the main device is accessed
                # before the response from the device is parsed.
                await self.main_device_added_event.wait()
            await self.hub.update()
            self.async_add_listener(lambda: None, None)
        except (TimeoutError, EheimDigitalClientError) as err:
            raise ConfigEntryNotReady from err

    @override
    async def _async_update_data(self) -> None:
        try:
            await self.hub.update()
        except ClientError as ex:
            for a in self.device_coordinators.values():
                for coordinator in a.values():
                    coordinator.async_set_update_error(ex)
            raise UpdateFailed from ex


class EheimDigitalDeviceUpdateCoordinator[_DeviceT: EheimDigitalDevice](
    DataUpdateCoordinator[_DeviceT]
):
    """An EHEIM Digital device update coordinator."""

    main_coordinator: EheimDigitalUpdateCoordinator
    msg_title: MsgTitle

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EheimDigitalConfigEntry,
        main_coordinator: EheimDigitalUpdateCoordinator,
        device: _DeviceT,
        msg_title: MsgTitle,
    ) -> None:
        """Initialize an EHEIM Digital device update coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{device.mac_address}_{msg_title}",
            update_interval=None,
        )
        self.main_coordinator = main_coordinator
        self.data = device
        self.msg_title = msg_title
