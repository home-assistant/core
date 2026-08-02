"""Base class for Mikrotik routers entities."""

from yarl import URL

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import MikrotikDataUpdateCoordinator


class MikrotikBaseEntity(CoordinatorEntity[MikrotikDataUpdateCoordinator]):
    """Base class for all Mikrotik entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MikrotikDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description

        self._serial = coordinator.api.serial_number

    def _base_device_info(self) -> DeviceInfo:
        """Return the device info fields shared by all Mikrotik devices."""
        coordinator = self.coordinator
        return DeviceInfo(
            configuration_url=URL.build(
                scheme="http",
                host=coordinator.host,
            ),
            manufacturer="Mikrotik",
            model=coordinator.model,
            sw_version=coordinator.firmware,
            serial_number=self._serial,
        )


class MikrotikEntity(MikrotikBaseEntity):
    """Base class for Mikrotik entities."""

    def __init__(
        self,
        coordinator: MikrotikDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, description)
        self._attr_device_info = DeviceInfo(
            **self._base_device_info(),
            identifiers={(DOMAIN, self._serial)},
            name=coordinator.hostname,
        )
        self._attr_unique_id = f"{self._serial}_{description.key}"


class MikrotikDeviceEntity(MikrotikBaseEntity):
    """Base class for Mikrotik device entities."""

    def __init__(
        self,
        coordinator: MikrotikDataUpdateCoordinator,
        description: EntityDescription,
        interface: dict,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, description)

        name = interface.get("name")
        ident = f"{slugify(interface.get('mac-address'))}_{name}"

        self._attr_device_info = DeviceInfo(
            **self._base_device_info(),
            identifiers={(DOMAIN, ident)},
            name=name,
            via_device=(DOMAIN, coordinator.api.serial_number),
        )
        self._attr_unique_id = ident
        self._attr_name = name
        self._interface = interface
