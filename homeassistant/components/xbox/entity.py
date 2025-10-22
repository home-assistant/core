"""Base Sensor for the Xbox Integration."""

from __future__ import annotations

from xbox.webapi.api.provider.smartglass.models import ConsoleType, SmartglassConsole

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ConsoleData, Person, XboxUpdateCoordinator

MAP_MODEL = {
    ConsoleType.XboxOne: "Xbox One",
    ConsoleType.XboxOneS: "Xbox One S",
    ConsoleType.XboxOneSDigital: "Xbox One S All-Digital",
    ConsoleType.XboxOneX: "Xbox One X",
    ConsoleType.XboxSeriesS: "Xbox Series S",
    ConsoleType.XboxSeriesX: "Xbox Series X",
}


class XboxBaseEntity(CoordinatorEntity[XboxUpdateCoordinator]):
    """Base Sensor for the Xbox Integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: XboxUpdateCoordinator,
        xuid: str,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize Xbox entity."""
        super().__init__(coordinator)
        self.xuid = xuid
        self.entity_description = entity_description

        self._attr_unique_id = f"{xuid}_{entity_description.key}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, xuid)},
            manufacturer="Microsoft Corporation",
            model="Xbox Network",
            name=self.data.gamertag,
        )

    @property
    def data(self) -> Person:
        """Return coordinator data for this console."""
        return self.coordinator.data.presence[self.xuid]


class XboxConsoleBaseEntity(CoordinatorEntity[XboxUpdateCoordinator]):
    """Console base entity for the Xbox integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        console: SmartglassConsole,
        coordinator: XboxUpdateCoordinator,
    ) -> None:
        """Initialize the Xbox Console entity."""

        super().__init__(coordinator)
        self.client = coordinator.client
        self._console = console

        self._attr_name = None
        self._attr_unique_id = console.id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, console.id)},
            manufacturer="Microsoft Corporation",
            model=MAP_MODEL.get(self._console.console_type, "Unknown"),
            name=console.name,
        )

    @property
    def data(self) -> ConsoleData:
        """Return coordinator data for this console."""
        return self.coordinator.data.consoles[self._console.id]
