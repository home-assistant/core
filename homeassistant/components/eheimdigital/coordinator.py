"""Data update coordinator for the EHEIM Digital integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, NamedTuple

from eheimdigital.device import EheimDigitalDevice
from eheimdigital.hub import EheimDigitalHub
from eheimdigital.types import EheimDeviceType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER

PLATFORMS_PER_DEVICE_TYPE = {
    EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E: [Platform.LIGHT]
}

type AsyncSetupDeviceEntitiesCallback = Callable[
    [EheimDigitalUpdateCoordinator, str, AddEntitiesCallback], Coroutine[Any, Any, None]
]


class CallbackTuple(NamedTuple):
    """A tuple for the platform setup callbacks."""

    async_setup_device_entities: AsyncSetupDeviceEntitiesCallback
    add_entities_callback: AddEntitiesCallback


class EheimDigitalUpdateCoordinator(
    DataUpdateCoordinator[dict[str, EheimDigitalDevice]]
):
    """The EHEIM Digital data update coordinator."""

    platform_callbacks: dict[Platform, CallbackTuple]
    config_entry: ConfigEntry
    hub: EheimDigitalHub
    known_devices: set[str]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the EHEIM Digital data update coordinator."""
        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )
        self.hub = EheimDigitalHub(
            host=self.config_entry.data[CONF_HOST],
            session=async_get_clientsession(hass),
            loop=hass.loop,
            receive_callback=self._async_receive_callback,
            device_found_callback=self._async_device_found,
        )
        self.known_devices = set()
        self.platform_callbacks = {}

    def add_platform_callbacks(
        self,
        platform: Platform,
        async_setup_device_entities: AsyncSetupDeviceEntitiesCallback,
        add_entities_callback: AddEntitiesCallback,
    ) -> None:
        """Add the setup callbacks from a specific platform."""
        if platform not in self.platform_callbacks:
            self.platform_callbacks[platform] = CallbackTuple(
                async_setup_device_entities, add_entities_callback
            )

    async def _async_device_found(
        self, device_address: str, device_type: EheimDeviceType
    ) -> None:
        """Set up a new device found.

        This function is called from the library whenever a new device is added.
        """

        if (
            device_address not in self.known_devices
            and device_type in PLATFORMS_PER_DEVICE_TYPE
        ):
            for platform in PLATFORMS_PER_DEVICE_TYPE[device_type]:
                await self.platform_callbacks[platform].async_setup_device_entities(
                    self,
                    device_address,
                    self.platform_callbacks[platform].add_entities_callback,
                )

    async def _async_receive_callback(self) -> None:
        self.async_set_updated_data(self.hub.devices)

    async def _async_setup(self) -> None:
        await self.hub.connect()
        await self.hub.update()

    async def _async_update_data(self) -> dict[str, EheimDigitalDevice]:
        await self.hub.update()
        return self.data
