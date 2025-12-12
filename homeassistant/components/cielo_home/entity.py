"""Base entity for Cielo integration."""

from __future__ import annotations

from time import time
from typing import Any, Final

from cieloconnectapi.model import CieloDevice

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CieloDataUpdateCoordinator

FRESHNESS_INTERVAL: Final[int] = 5


class CieloBaseEntity(CoordinatorEntity[CieloDataUpdateCoordinator]):
    """Representation of a Cielo Base Entity."""

    _attr_has_entity_name: bool = True

    _device_id: str
    _client: Any
    _last_known: CieloDevice | None
    last_action: dict[str, Any] | None
    last_action_timestamp: int
    last_fetched_timestamp: int | None

    def __init__(
        self,
        coordinator: CieloDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initiate Cielo Base Entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._client = coordinator.client
        self._last_known = None
        self.last_action = None
        self.last_action_timestamp = int(time())
        self.last_fetched_timestamp = None

    @property
    def client(self) -> Any:
        """Return the API client bound to this entity's current device."""
        if self._client and self.device_data:
            self._client.device_data = self.device_data
        return self._client

    @property
    def device_data(self) -> CieloDevice | None:
        """Return the device data from the coordinator."""
        current_time = int(time())

        if (
            self._last_known is not None
            and self.last_fetched_timestamp is not None
            and (current_time - self.last_fetched_timestamp < FRESHNESS_INTERVAL)
        ):
            return self._last_known

        # Fetch from Coordinator
        data = self.coordinator.data.parsed
        device = data.get(self._device_id)

        if device is None:
            return None

        # Cache the fetched data
        self._last_known = device
        self.last_fetched_timestamp = current_time

        # Action Flicker Masking
        if (
            (current_time - self.last_action_timestamp < FRESHNESS_INTERVAL)
            and self.last_action
            and device.ac_states is not None
        ):
            device.apply_update(self.last_action)

        return device

    @property
    def device_info(self) -> DeviceInfo:
        """Return a basic device description for the entity's device data."""
        dev_data = self.device_data

        if dev_data is None:
            return DeviceInfo(identifiers={(DOMAIN, self._device_id)})

        return DeviceInfo(
            identifiers={(DOMAIN, dev_data.mac_address)},
            manufacturer="Cielo",
            name=dev_data.name,
        )


class CieloDeviceBaseEntity(CieloBaseEntity):
    """Representation of a Cielo Device."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device details for the device registry."""
        dev_data = self.device_data

        if dev_data is None:
            return DeviceInfo(identifiers={(DOMAIN, self._device_id)})

        return DeviceInfo(
            identifiers={(DOMAIN, dev_data.id)},
            name=dev_data.name,
            connections={(CONNECTION_NETWORK_MAC, dev_data.mac_address)},
            manufacturer="Cielo",
            configuration_url="https://home.cielowigle.com/",
            suggested_area=dev_data.name,
        )
