"""Buttons for Meraki Dashboard infrastructure devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import (
    MerakiDashboardApiAuthError,
    MerakiDashboardApiConnectionError,
    MerakiDashboardApiError,
)
from .const import DOMAIN
from .coordinator import (
    MerakiDashboardConfigEntry,
    MerakiDashboardDataUpdateCoordinator,
    MerakiDashboardInfrastructureDevice,
)


@dataclass(frozen=True, kw_only=True)
class MerakiDashboardButtonDescription(ButtonEntityDescription):
    """Description for Meraki Dashboard button entities."""

    action: str


BUTTONS: tuple[MerakiDashboardButtonDescription, ...] = (
    MerakiDashboardButtonDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        action="reboot",
    ),
    MerakiDashboardButtonDescription(
        key="ping",
        entity_category=EntityCategory.DIAGNOSTIC,
        action="ping",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MerakiDashboardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meraki Dashboard button entities."""
    coordinator = config_entry.runtime_data
    tracked_unique_ids: set[str] = set()

    @callback
    def async_add_new_entities() -> None:
        entities: list[MerakiDashboardDeviceActionButton] = []
        for serial in coordinator.data.infrastructure_devices:
            for description in BUTTONS:
                unique_id = f"{serial}_{description.key}"
                if unique_id in tracked_unique_ids:
                    continue
                tracked_unique_ids.add(unique_id)
                entities.append(
                    MerakiDashboardDeviceActionButton(coordinator, serial, description)
                )

        if entities:
            async_add_entities(entities)

    async_add_new_entities()
    config_entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))


class MerakiDashboardDeviceActionButton(
    CoordinatorEntity[MerakiDashboardDataUpdateCoordinator], ButtonEntity
):
    """Representation of a Meraki infrastructure action button."""

    _attr_has_entity_name = True
    entity_description: MerakiDashboardButtonDescription

    def __init__(
        self,
        coordinator: MerakiDashboardDataUpdateCoordinator,
        serial: str,
        description: MerakiDashboardButtonDescription,
    ) -> None:
        """Initialize action button."""
        super().__init__(coordinator)
        self._serial = serial
        self.entity_description = description
        self._attr_unique_id = f"{serial}_{description.key}"
        self._last_result: str | None = None

    @property
    def _device(self) -> MerakiDashboardInfrastructureDevice | None:
        """Return current device details."""
        return self.coordinator.data.infrastructure_devices.get(self._serial)

    @property
    def name(self) -> str:
        """Return entity name."""
        if self.entity_description.key == "reboot":
            return "Reboot"
        return "Ping"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device is not None and super().available

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return linked device info."""
        if (device := self._device) is None:
            return None
        connections = set()
        if device.mac:
            connections.add((CONNECTION_NETWORK_MAC, device.mac))
        return DeviceInfo(
            identifiers={(DOMAIN, device.serial)},
            connections=connections,
            manufacturer="Cisco Meraki",
            model=device.model,
            name=device.name or device.serial,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {"last_result": self._last_result}

    async def async_press(self) -> None:
        """Press the action button."""
        try:
            if self.entity_description.action == "reboot":
                result = await self.coordinator.api.async_reboot_device(self._serial)
                self._last_result = (
                    "queued" if result is None else str(result.get("success"))
                )
            else:
                result = await self.coordinator.api.async_ping_device(self._serial)
                self._last_result = (
                    "queued" if result is None else str(result.get("status"))
                )
        except MerakiDashboardApiAuthError as err:
            raise HomeAssistantError("Authentication failed") from err
        except MerakiDashboardApiConnectionError as err:
            raise HomeAssistantError("Cannot connect to Meraki") from err
        except MerakiDashboardApiError as err:
            raise HomeAssistantError(f"Meraki API error: {err}") from err
