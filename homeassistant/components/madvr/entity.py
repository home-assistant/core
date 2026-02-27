"""Entity base classes for madVR Envy."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from madvr_envy import exceptions

from .const import DOMAIN, MANUFACTURER, MODEL, NAME
from .coordinator import MadvrEnvyCoordinator


class MadvrEnvyEntity(CoordinatorEntity[MadvrEnvyCoordinator]):
    """Common entity behavior for madVR Envy entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: MadvrEnvyCoordinator, entity_key: str) -> None:
        super().__init__(coordinator)
        self._entity_key = entity_key
        self._client = coordinator.client

        device_id = coordinator.mac
        mac = self._mac_address
        self._attr_unique_id = f"{device_id}_{entity_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=self.data.get("version"),
            configuration_url=f"http://{self._client.host}",
            connections={(CONNECTION_NETWORK_MAC, mac)} if mac else None,
        )

    @property
    def available(self) -> bool:
        return bool(self.data.get("available"))

    @property
    def data(self) -> dict[str, Any]:
        if self.coordinator.data is None:
            return {}
        return self.coordinator.data

    @property
    def _device_id(self) -> str:
        return self.coordinator.mac

    @property
    def _mac_address(self) -> str | None:
        mac = self.data.get("mac_address")
        if isinstance(mac, str) and mac:
            return mac
        if self.coordinator.mac:
            return self.coordinator.mac
        return None

    async def _execute(self, command_name: str, command: Callable[[], Any]) -> None:
        try:
            await command()
        except (
            TimeoutError,
            exceptions.NotConnectedError,
            exceptions.CommandRejectedError,
            exceptions.ConnectionFailedError,
            exceptions.ConnectionTimeoutError,
        ) as err:
            raise HomeAssistantError(f"{command_name} failed: {err}") from err
